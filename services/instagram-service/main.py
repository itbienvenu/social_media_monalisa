import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlalchemy
import uuid
import datetime

from services.instagram_service.db import database, metadata, SocialTarget
from services.instagram_service.logic import post_to_instagram, InstagramClient, FACEBOOK_API_VERSION
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instagram-service")

mq = MessageQueue("instagram-service")

from libs.common.db import connect_db_with_retry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    await connect_db_with_retry(database)
    
    logger.info(f"DEBUG: DATABASE_URL={database.url}")
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
    except Exception as e:
        logger.warning(f"Table creation skipped or already completed: {e}")
    
    # Start Consumer
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    # await database.disconnect()

app = FastAPI(title="Instagram Service", lifespan=lifespan)

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

async def consume_loop():
    logger.info("Starting Instagram Service Consumer...")
    while True:
        try:
            await mq.subscribe("posts.instagram", handle_post_event)
            logger.info("Successfully subscribed to posts.instagram")
            break 
        except Exception as e:
            logger.error(f"Failed to subscribe to RabbitMQ: {e}. Retrying in 5s...")
            await asyncio.sleep(5)
            
    while True:
        await asyncio.sleep(1)

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    media_url = message.get("media_url")
    user_id = message.get("user_id")
    if not user_id:
        logger.error("User ID missing in message")
        return
    
    # Fetch User Credential (IG Target)
    # We look for an Instagram target
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.platform == "instagram")
    )
    # In reality there could be multiple, we pick one or handle all. 
    # For MVP we pick the first one.
    target = await database.fetch_one(query)
    
    if target:
        await post_to_instagram(post_id, content, target['access_token'], target['target_id'], media_url)
    else:
        logger.error(f"No credentials found for user {user_id}")
        await mq.publish("posts.instagram.failed", {"post_id": post_id, "reason": "no_credentials"})

# --- OAuth Endpoints ---

@app.post("/auth/connect")
async def connect_instagram(user_id: str):
    """
    Redirects to Facebook Auth, but we track that the intent is Instagram connectivity.
    """
    import os
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    # Use BASE_URL from env
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/instagram/callback"
    
    # Scopes needed for Instagram Graph API
    SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
    
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={FACEBOOK_APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"state={user_id}&"
        f"scope={SCOPES}"
    )
    
    return {"url": auth_url}

@app.get("/auth/callback")
async def instagram_callback(code: str, state: str):
    import httpx
    import os
    
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
    
    if not code:
         raise HTTPException(status_code=400, detail="Missing code")

    user_id = state
    
    user_access_token = None
    
    # 1. Exchange Code for Access Token (Same as FB)
    if FACEBOOK_APP_ID and FACEBOOK_APP_SECRET:
         api_version = os.getenv("FACEBOOK_API_VERSION", "v18.0")
         base_url = os.getenv("BASE_URL", "http://localhost:8000")
         token_url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
         params = {
             "client_id": FACEBOOK_APP_ID,
             "redirect_uri": f"{base_url}/auth/instagram/callback",
             "client_secret": FACEBOOK_APP_SECRET,
             "code": code
         }
         async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(token_url, params=params)
                resp.raise_for_status()
                user_access_token = resp.json().get("access_token")
            except Exception as e:
                logger.error(f"Failed to exchange token with Facebook for IG: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    if not user_access_token:
         raise HTTPException(status_code=500, detail="Configuration missing or Auth failed")
    
    # 1. Fetch connected IG Business Accounts
    client = InstagramClient(user_access_token, "me") # "me" only for account fetch context
    try:
        ig_accounts = await client.get_user_accounts()
        logger.info(f"Found {len(ig_accounts)} IG accounts for user {user_id}")
        
        for ig in ig_accounts:
            # Store Target
            t_query = SocialTarget.insert().values(
                id=uuid.uuid4(),
                user_id=user_id,
                target_id=ig['id'],
                target_name=ig['name'],
                access_token=user_access_token, # We use the User token (or Page token if applicable, but usually User token works for IG Graph)
                page_id=ig['page_id'],
                platform="instagram"
            )
            try:
                await database.execute(t_query)
            except Exception:
                pass
            
        # return {"status": "connected", "user_id": user_id, "accounts_linked": len(ig_accounts)}
        redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
        return RedirectResponse(url=redirect_url)
            
    except Exception as e:
        logger.error(f"Failed to fetch IG accounts: {e}")
        return {"status": "error", "reason": str(e)}
    finally:
        await client.close()

@app.get("/credentials")
async def get_credentials(user_id: str):
    query = SocialTarget.select().where(SocialTarget.c.user_id == user_id)
    cred = await database.fetch_one(query)
    if cred:
        return {"connected": True, "platform": "instagram", "id": str(cred['id'])}
    return {"connected": False, "platform": "instagram"}

@app.delete("/credentials")
async def delete_credentials(user_id: str):
    query = SocialTarget.delete().where(SocialTarget.c.user_id == user_id)
    await database.execute(query)
    return {"status": "deleted"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
