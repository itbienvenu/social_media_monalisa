import asyncio
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
import sqlalchemy
import uuid
import datetime

from services.tiktok_service.db import database, metadata, SocialCredential
from services.tiktok_service.logic import post_to_tiktok
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-service")

mq = MessageQueue("tiktok-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    logger.info(f"DEBUG: DATABASE_URL={database.url}")
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    
    # Start Consumer
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    # await database.disconnect()

app = FastAPI(title="TikTok Service", lifespan=lifespan)

async def consume_loop():
    logger.info("Starting TikTok Service Consumer...")
    while True:
        try:
            await mq.subscribe("posts.tiktok", handle_post_event)
            logger.info("Successfully subscribed to posts.tiktok")
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
    media_url = message.get("media_url") # Required for TikTok
    user_id = message.get("user_id", "test-user")
    
    # Fetch User Credential
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    
    if cred:
        await post_to_tiktok(post_id, content, cred['access_token'], cred['open_id'], media_url)
    else:
        logger.error(f"No credentials found for user {user_id}")
        await mq.publish("posts.tiktok.failed", {"post_id": post_id, "reason": "no_credentials"})

# --- OAuth Endpoints ---

@app.post("/auth/connect")
async def connect_tiktok(user_id: str):
    """
    Returns the TikTok OAuth URL.
    """
    # MOCK implementation
    # Real URL structure: https://www.tiktok.com/v2/auth/authorize/client_key=...
    return {"url": f"http://localhost:8000/auth/tiktok/callback?code=mock_tiktok_code_for_{user_id}&state={user_id}"}

@app.get("/auth/callback")
async def tiktok_callback(code: str, state: str):
    user_id = state
    import httpx
    import os
    
    CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
    CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
    
    auth_token = None
    open_id = None
    
    if CLIENT_KEY and CLIENT_SECRET:
         token_url = "https://open.tiktokapis.com/v2/oauth/token/"
         headers = {"Content-Type": "application/x-www-form-urlencoded"}
         data = {
             "client_key": CLIENT_KEY,
             "client_secret": CLIENT_SECRET,
             "code": code,
             "grant_type": "authorization_code",
             "redirect_uri": "http://localhost:8000/auth/tiktok/callback"
         }
         async with httpx.AsyncClient() as client:
             try:
                 resp = await client.post(token_url, data=data, headers=headers)
                 resp.raise_for_status()
                 result = resp.json() 
                 # TikTok response structure: { "data": { "access_token": "...", "open_id": "...", ... } }
                 if "data" in result:
                     auth_token = result["data"].get("access_token")
                     open_id = result["data"].get("open_id")
             except Exception as e:
                 logger.error(f"TikTok Auth Failed: {e}")
                 if os.getenv("MOCK_MODE") != "true":
                      return {"status": "error", "reason": str(e)}

    # Fallback / Mock
    if not auth_token and os.getenv("MOCK_MODE") == "true":
         auth_token = f"tk_mock_token_{user_id}"
         open_id = f"tk_mock_openid_{user_id}"

    if not auth_token:
         raise HTTPException(status_code=500, detail="Auth failed")

    # Store Credential
    timestamp = datetime.datetime.utcnow()
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        open_id=open_id,
        access_token=auth_token,
        refresh_token="ref_mock_tk",
        expires_at=timestamp + datetime.timedelta(days=1),
        refresh_expires_at=timestamp + datetime.timedelta(days=365),
    )
    await database.execute(query)
    
    return {"status": "connected", "user_id": user_id, "open_id": open_id}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
