import asyncio
import logging
from fastapi import FastAPI
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

# --- OAuth Endpoints ---

@app.post("/auth/connect")
async def connect_linkedin(user_id: str):
    """
    Returns LinkedIn OAuth URL.
    """
    # Real URL: https://www.linkedin.com/oauth/v2/authorization...
    # Scopes: w_member_social, r_liteprofile (or r_basicprofile)
    scopes = "w_member_social,r_liteprofile"
    return {"url": f"http://localhost:8000/auth/linkedin/callback?code=mock_linkedin_code_for_{user_id}&state={user_id}&scope={scopes}"}

@app.get("/auth/callback")
async def linkedin_callback(code: str, state: str):
    user_id = state
    import httpx
    import os
    
    CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
    CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
    
    mock_urn = None
    mock_token = None

    if CLIENT_ID and CLIENT_SECRET:
         token_url = "https://www.linkedin.com/oauth/v2/accessToken"
         params = {
             "grant_type": "authorization_code",
             "code": code,
             "redirect_uri": "http://localhost:8000/auth/linkedin/callback",
             "client_id": CLIENT_ID,
             "client_secret": CLIENT_SECRET
         }
         async with httpx.AsyncClient() as client:
             try:
                 resp = await client.post(token_url, data=params) # LinkedIn wants POST form data? or params? Docs say POST x-www-form-urlencoded
                 resp.raise_for_status()
                 data = resp.json()
                 mock_token = data.get("access_token")
                 expires_in = data.get("expires_in", 5184000) # 60 days
                 
                 # Now fetch Profile to get URN
                 if mock_token:
                      headers = {"Authorization": f"Bearer {mock_token}"}
                      p_resp = await client.get("https://api.linkedin.com/v2/me", headers=headers)
                      p_resp.raise_for_status()
                      # id is usually "person_urn_suffix" e.g "12345" result is "urn:li:person:12345"
                      # or API returns full URN? v2/me returns "id"
                      p_data = p_resp.json()
                      mock_urn = p_data.get("id") # Just the ID part usually
             except Exception as e:
                 logger.error(f"LinkedIn Auth Failed: {e}")
                 if os.getenv("MOCK_MODE") != "true":
                      return {"status": "error", "reason": str(e)}

    # Fallback / Mock
    if not mock_token and os.getenv("MOCK_MODE") == "true":
        mock_urn = f"mock_person_urn_{user_id}"
        mock_token = f"atok_mock_linkedin_{user_id}"
    
    if not mock_token:
         raise HTTPException(status_code=500, detail="Auth failed")

    timestamp = datetime.datetime.utcnow()
    expires_at = timestamp + datetime.timedelta(seconds=5184000) # Default 60 days
    
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        linkedin_urn=mock_urn, # If real, this is ID. Post Logic handles prefix.
        access_token=mock_token,
        refresh_token="ref_mock_li", # LinkedIn v2 access token is self-contained usually, refresh flow specific.
        expires_at=expires_at,
        scope="w_member_social",
        platform="linkedin"
    )
    await database.execute(query)
    
    return {"status": "connected", "user_id": user_id, "linkedin_urn": mock_urn}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
