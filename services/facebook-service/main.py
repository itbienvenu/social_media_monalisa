import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request
from services.facebook_service.logic import post_to_facebook
from services.facebook_service.db import database, metadata, SocialCredential
from libs.common.messaging import MessageQueue
import sqlalchemy
from contextlib import asynccontextmanager
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facebook-service")

mq = MessageQueue("facebook-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    print(f"DEBUG: DATABASE_URL={database.url}", flush=True)
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    
    # Start Consumer Background Task
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    # await database.disconnect()

app = FastAPI(title="Facebook Service", lifespan=lifespan)

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

from services.facebook_service.db import database, metadata, SocialCredential, SocialTarget
from services.facebook_service.logic import post_to_facebook, FacebookClient

# ... existing imports ...

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    user_id = message.get("user_id", "test-user") 
    
    # Fetch Page Token (Target)
    # Strategy: Find the first 'page' target for this user
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.target_type == "page")
    )
    target = await database.fetch_one(query)
    
    if target:
        await post_to_facebook(post_id, content, target['access_token'], target['target_id'])
    else:
        # Fallback to User Token (which might fail for posting but good for logging)
        # OR just error out because we want to enforce Page posting
        logger.error(f"No Page target found for user {user_id}")
        await mq.publish("posts.facebook.failed", {"post_id": post_id, "reason": "no_page_target_found"})

# ...

@app.post("/auth/connect")
async def connect_facebook(user_id: str):
    """
    Returns the Facebook OAuth URL.
    """
    import os
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    # Use BASE_URL from env or default to localhost
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    # Should match the one configured in Facebook App > Facebook Login > Settings > Valid OAuth Redirect URIs
    REDIRECT_URI = f"{base_url}/auth/facebook/callback"
    
    # Scopes for Page Management
    SCOPES = "pages_show_list,pages_read_engagement,pages_manage_posts,pages_manage_metadata"
    
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={FACEBOOK_APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"state={user_id}&"
        f"scope={SCOPES}"
    )
    
    return {"url": auth_url}

@app.get("/auth/callback")
async def facebook_callback(code: str, state: str):
    """
    Receives code, exchanges for token, fetches Pages, stores everything.
    """
    import httpx
    import os
    
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
    
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    user_id = state

    user_access_token = None
    
    # 1. Exchange Code for Access Token
    if FACEBOOK_APP_ID and FACEBOOK_APP_SECRET:
        api_version = os.getenv("FACEBOOK_API_VERSION", "v18.0")
        token_url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
        params = {
            "client_id": FACEBOOK_APP_ID,
            "redirect_uri": f"{Request.base_url}auth/callback", # Ensure this matches handling
            "client_secret": FACEBOOK_APP_SECRET,
            "code": code
        }
        # Note: Redirect URI in local dev might need to be hardcoded or passed via env if simple concatenation fails
        # For this implementation we assume standard localhost callback pattern or flexible validation
        # But commonly we just need the exact string configured in FB App.
        # Custom BASE_URL logic
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        params["redirect_uri"] = f"{base_url}/auth/facebook/callback"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(token_url, params=params)
                resp.raise_for_status()
                user_access_token = resp.json().get("access_token")
            except Exception as e:
                logger.error(f"Failed to exchange token with Facebook: {e}")
                if os.getenv("MOCK_MODE") == "true":
                     logger.warning("Falling back to MOCK token due to error (MOCK_MODE=true)")
                     pass
                else:
                    return {"status": "error", "reason": "auth_exchange_failed", "details": str(e)}

    # Fallback for Mock Mode if configured and real exchange failed or keys missing
    if not user_access_token:
        if os.getenv("MOCK_MODE") == "true" or not (FACEBOOK_APP_ID and FACEBOOK_APP_SECRET):
             user_access_token = f"EAAB_mock_user_token_for_{user_id}"
        else:
             raise HTTPException(status_code=500, detail="Facebook configuration missing and Not in Mock Mode")

    # Store User Credential
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        platform="facebook",
        access_token=user_access_token,
        page_id=None 
    )
    await database.execute(query)
    
    # Fetch User Pages
    client = FacebookClient(user_access_token, "me")
    try:
        pages = await client.get_user_pages()
        logger.info(f"Found {len(pages)} pages for user {user_id}")
        
        for page in pages:
            # Check for dupes if re-authing? For MVP we just insert and maybe fail or we should UPSERT.
            # Simpler: Delete old targets for this user/platform first? 
            # Ideally: UPSERT. databases/sqlalchemy async support for upsert varies. 
            # We will catch unique violation or just insert. 
            # Assuming Clean state for demo.
            
            t_query = SocialTarget.insert().values(
                id=uuid.uuid4(),
                user_id=user_id,
                target_id=page['id'],
                target_name=page['name'],
                target_type="page",
                access_token=page['access_token'],
                platform="facebook"
            )
            try:
                await database.execute(t_query)
            except Exception:
                pass # Ignore dupes for now
            
    except Exception as e:
        logger.error(f"Failed to fetch pages: {e}")
    finally:
        await client.close()
    
    return {"status": "connected", "user_id": user_id, "pages_fetched": len(pages) if 'pages' in locals() else 0}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
