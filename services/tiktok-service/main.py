import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlalchemy
import uuid
import datetime
import os
import secrets
import hashlib
import base64
import redis.asyncio as redis

from services.tiktok_service.db import database, metadata, SocialCredential
from services.tiktok_service.logic import post_to_tiktok
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-service")

mq = MessageQueue("tiktok-service")
redis_client = None

from libs.common.db import connect_db_with_retry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    logger.info(f"DEBUG: DATABASE_URL={database.url}")
    
    # Use sync driver for create_all
    sync_db_url = str(database.url).replace("+asyncpg", "")
    engine = sqlalchemy.create_engine(sync_db_url)
    metadata.create_all(engine)
    
    await connect_db_with_retry(database)
    
    # Init Redis
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/1")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    logger.info(f"Connected to Redis at {redis_url}")

    # Start Consumer
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    if redis_client:
        await redis_client.close()
    # await database.disconnect()

app = FastAPI(title="TikTok Service", lifespan=lifespan)

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
    user_id = message.get("user_id")
    if not user_id:
        logger.error("User ID missing in message")
        return
    
    # Fetch User Credential
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    
    if cred:
        await post_to_tiktok(post_id, content, cred['access_token'], cred['open_id'], media_url)
    else:
        logger.error(f"No credentials found for user {user_id}")
        await mq.publish("posts.tiktok.failed", {"post_id": post_id, "reason": "no_credentials"})

# --- PKCE Helper ---
def generate_pkce_pair():
    # Generate random verifier
    verifier = secrets.token_urlsafe(32)
    # Hash with SHA256
    digest = hashlib.sha256(verifier.encode()).digest()
    # Base64 URL encode without padding
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge

# --- OAuth Endpoints ---

@app.post("/auth/connect")
async def connect_tiktok(user_id: str):
    """
    Returns the TikTok OAuth URL with PKCE.
    """
    CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
    # Redirect URI must match TikTok App settings
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/tiktok/callback"
    
    # Scopes
    SCOPES = "user.info.basic,video.publish,video.upload"
    
    # Generate PKCE
    verifier, challenge = generate_pkce_pair()
    
    # Store verifier in Redis using state as key
    state = user_id
    await redis_client.setex(f"tiktok_pkce_{state}", 600, verifier)
    
    import urllib.parse
    params = {
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }
    
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
    logger.info(f"Generated TikTok Auth URL: {auth_url}")
    
    return {"url": auth_url}

@app.get("/auth/callback")
async def tiktok_callback(code: str, state: str):
    user_id = state
    import httpx
    
    CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
    CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/tiktok/callback"
    
    if not code:
         raise HTTPException(status_code=400, detail="Missing code")

    # Retrieve PKCE Verifier
    verifier = await redis_client.get(f"tiktok_pkce_{state}")
    if not verifier and os.getenv("MOCK_MODE") != "true":
        logger.error(f"Missing or expired PKCE verifier for state {state}")
        # In mock mode we might skip, but better to error out on real flows
        raise HTTPException(status_code=400, detail="Session expired or invalid state")

    auth_token = None
    open_id = None
    refresh_token = None
    expires_in_seconds = 86400

    if CLIENT_KEY and CLIENT_SECRET:
         token_url = "https://open.tiktokapis.com/v2/oauth/token/"
         headers = {"Content-Type": "application/x-www-form-urlencoded"}
         data = {
             "client_key": CLIENT_KEY,
             "client_secret": CLIENT_SECRET,
             "code": code,
             "grant_type": "authorization_code",
             "redirect_uri": REDIRECT_URI,
             "code_verifier": verifier
         }
         async with httpx.AsyncClient() as client:
             try:
                 resp = await client.post(token_url, data=data, headers=headers)
                 resp.raise_for_status()
                 result = resp.json()
                 logger.info(f"TikTok Token Response: {result}") 
                 # TikTok response structure: { "data": { "access_token": "...", "open_id": "...", ... } } OR direct flat response
                 if "data" in result:
                     auth_token = result["data"].get("access_token")
                     open_id = result["data"].get("open_id")
                     refresh_token = result["data"].get("refresh_token")
                     expires_in_seconds = result["data"].get("expires_in", 86400)
                 else:
                     auth_token = result.get("access_token")
                     open_id = result.get("open_id")
                     refresh_token = result.get("refresh_token")
                     expires_in_seconds = result.get("expires_in", 86400)
             except Exception as e:
                 logger.error(f"TikTok Auth Failed: {e}")
                 # Fallback only if strictly in mock mode
                 if os.getenv("MOCK_MODE") != "true":
                      raise HTTPException(status_code=400, detail=f"TikTok Auth failed: {str(e)}")

    # Fallback / Mock
    if not auth_token and os.getenv("MOCK_MODE") == "true":
         auth_token = f"tk_mock_token_{user_id}"
         open_id = f"tk_mock_openid_{user_id}"
         refresh_token = f"ref_mock_tk"

    if not auth_token:
         raise HTTPException(status_code=500, detail="TikTok Auth failed")

    # Store Credential
    timestamp = datetime.datetime.utcnow()
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        open_id=open_id,
        access_token=auth_token,
        refresh_token=refresh_token,
        expires_at=timestamp + datetime.timedelta(seconds=expires_in_seconds),
        refresh_expires_at=timestamp + datetime.timedelta(days=365), # Refresh tokens endure
    )
    await database.execute(query)
    
    # return {"status": "connected", "user_id": user_id, "open_id": open_id}
    redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
    return RedirectResponse(url=redirect_url)

@app.get("/credentials")
async def get_credentials(user_id: str):
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    if cred:
        return {"connected": True, "platform": "tiktok", "id": str(cred['id'])}
    return {"connected": False, "platform": "tiktok"}

@app.delete("/credentials")
async def delete_credentials(user_id: str):
    query = SocialCredential.delete().where(SocialCredential.c.user_id == user_id)
    await database.execute(query)
    return {"status": "deleted"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
