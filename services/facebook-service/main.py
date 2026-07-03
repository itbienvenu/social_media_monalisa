import asyncio
import logging
import sqlalchemy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.facebook_service.logic import post_to_facebook
from services.facebook_service.db import database, metadata, SocialTarget
from services.facebook_service.routes import router as facebook_router
from libs.common.messaging import MessageQueue
from libs.common.logger import log_post_stage
from libs.common.db import connect_db_with_retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facebook-service")

mq = MessageQueue("facebook-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    await connect_db_with_retry(database)
    
    print(f"DEBUG: DATABASE_URL={database.url}", flush=True)
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
    except Exception as e:
        print(f"Table creation skipped or already completed: {e}", flush=True)
    
    # Start Consumer Background Task
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()

app = FastAPI(title="Facebook Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://subacidly-ungrilled-rosy.ngrok-free.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes router
app.include_router(facebook_router)

async def consume_loop():
    logger.info("Starting Facebook Service Consumer...")
    while True:
        try:
            await mq.subscribe("posts.facebook", handle_post_event)
            logger.info("Successfully subscribed to posts.facebook")
            break # Exit retry loop once subscribed (subscription is persistent)
        except Exception as e:
            logger.error(f"Failed to subscribe to RabbitMQ: {e}. Retrying in 5s...")
            await asyncio.sleep(5)
            
    while True:
        await asyncio.sleep(1)

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    user_id = message.get("user_id")
    media_url = message.get("media_url")
    media_urls = message.get("media_urls") or []
    is_reel = message.get("is_reel", False)
    if not media_urls and media_url:
        media_urls = [media_url]

    if not user_id:
        logger.error("User ID missing in message")
        return 
    
    await log_post_stage(
        database, post_id, "facebook", "event_received", "INFO",
        f"Event received by facebook-service. media_urls count: {len(media_urls)}"
    )
    
    # Fetch Page Token (Target)
    from libs.common.db_models import SocialTarget as CentralSocialTarget, SocialAccount as CentralSocialAccount
    from libs.common.security import decrypt_token
    import sqlalchemy

    facebook_page_id = message.get("facebook_page_id")
    target = None
    decrypted_token = None
    target_id = None

    if facebook_page_id:
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.target_id == facebook_page_id) &
            (CentralSocialTarget.c.platform == "facebook")
        )
        target = await database.fetch_one(query)

    if not target:
        # Try to find any facebook page in central targets first
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.platform == "facebook")
        )
        target = await database.fetch_one(query)

    if target:
        decrypted_token = decrypt_token(target['access_token'])
        target_id = target['target_id']
    else:
        # Fallback to local legacy table
        legacy_query = SocialTarget.select().where(
            (SocialTarget.c.user_id == user_id) & 
            (SocialTarget.c.target_type == "page")
        )
        legacy_target = await database.fetch_one(legacy_query)
        if legacy_target:
            decrypted_token = legacy_target['access_token']
            target_id = legacy_target['target_id']

    if decrypted_token:
        await post_to_facebook(post_id, content, decrypted_token, target_id, media_url=media_url, media_urls=media_urls, is_reel=is_reel)
    else:
        logger.error(f"No Page target found for user {user_id}")
        await log_post_stage(
            database, post_id, "facebook", "no_page_target", "ERROR",
            f"Failed to post: No Facebook Page target/credentials found in database for user_id={user_id}"
        )
        await mq.publish("posts.facebook.failed", {"post_id": post_id, "reason": "no_page_target_found"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
