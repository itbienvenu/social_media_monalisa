import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlalchemy
import uuid
import datetime

from services.linkedin_service.db import database, metadata, SocialCredential
from services.linkedin_service.logic import post_to_linkedin
from libs.common.messaging import MessageQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin-service")

mq = MessageQueue("linkedin-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"DEBUG: DATABASE_URL={database.url}")
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    # await database.disconnect()

app = FastAPI(title="LinkedIn Service", lifespan=lifespan)

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
    logger.info("Starting LinkedIn Service Consumer...")
    while True:
        try:
            await mq.subscribe("posts.linkedin", handle_post_event)
            logger.info("Successfully subscribed to posts.linkedin")
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
    user_id = message.get("user_id", "test-user")
    
    # Fetch User Credential
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    
    if cred:
        await post_to_linkedin(post_id, content, cred['access_token'], cred['linkedin_urn'], media_url)
    else:
        logger.error(f"No credentials found for user {user_id}")
        await mq.publish("posts.linkedin.failed", {"post_id": post_id, "reason": "no_credentials"})


@app.post("/auth/connect")
async def connect_linkedin(user_id: str):
    """
    Returns LinkedIn OAuth URL.
    """
    import os
    CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/linkedin/callback"
    
    SCOPES = "w_member_social,openid,profile,email"
    
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"state={user_id}&"
        f"scope={SCOPES}"
    )
    return {"url": auth_url}

@app.get("/auth/callback")
async def linkedin_callback(code: str, state: str):
    user_id = state
    import httpx
    import os
    
    CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
    CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/linkedin/callback"
    
    if not code:
         raise HTTPException(status_code=400, detail="Missing code")

    access_token = None
    urn = None

    if CLIENT_ID and CLIENT_SECRET:
         token_url = "https://www.linkedin.com/oauth/v2/accessToken"
         params = {
             "grant_type": "authorization_code",
             "code": code,
             "redirect_uri": REDIRECT_URI,
             "client_id": CLIENT_ID,
             "client_secret": CLIENT_SECRET
         }
         # LinkedIn expects Content-Type: application/x-www-form-urlencoded
         async with httpx.AsyncClient() as client:
             try:
                 resp = await client.post(token_url, data=params)
                 resp.raise_for_status()
                 data = resp.json()
                 access_token = data.get("access_token")
                 expires_in = data.get("expires_in", 5184000) # 60 days
                 
                 # Fetch Profile via OIDC UserInfo endpoint
                 if access_token:
                      headers = {"Authorization": f"Bearer {access_token}"}
                      # Modern OIDC endpoint
                      p_resp = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
                      p_resp.raise_for_status()
                      p_data = p_resp.json()
                      urn = p_data.get("sub") # 'sub' is the member ID in OIDC
             except Exception as e:
                 logger.error(f"LinkedIn Auth Failed: {e}")
                 # Fallback only if strictly in mock mode and actual auth failed
                 if os.getenv("MOCK_MODE") != "true":
                      return {"status": "error", "reason": "auth_exchange_failed", "details": str(e)}
 
    # Fallback / Mock
    if not access_token and os.getenv("MOCK_MODE") == "true":
        urn = f"mock_person_urn_{user_id}"
        access_token = f"atok_mock_linkedin_{user_id}"
    
    if not access_token:
         raise HTTPException(status_code=500, detail="LinkedIn Auth failed")

    # Store Credential
    timestamp = datetime.datetime.utcnow()
    expires_at = timestamp + datetime.timedelta(seconds=5184000)
    
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        linkedin_urn=urn, 
        access_token=access_token,
        refresh_token=None,
        expires_at=expires_at,
        scope="w_member_social",
        platform="linkedin"
    )
    await database.execute(query)
    
    # return {"status": "connected", "user_id": user_id, "linkedin_urn": urn}
    redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
    return RedirectResponse(url=redirect_url)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
