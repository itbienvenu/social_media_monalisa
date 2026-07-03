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
    media_urls = message.get("media_urls", [])
    user_id = message.get("user_id")
    if not user_id:
        logger.error("User ID missing in message")
        return
    
    # Fetch Page Token (Target)
    from libs.common.db_models import SocialTarget as CentralSocialTarget, SocialAccount as CentralSocialAccount
    from libs.common.security import decrypt_token
    import sqlalchemy

    linkedin_target_urn = message.get("linkedin_urn")
    target = None
    decrypted_token = None
    target_urn = None

    if linkedin_target_urn:
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.target_id == linkedin_target_urn) &
            (CentralSocialTarget.c.platform == "linkedin")
        )
        target = await database.fetch_one(query)

    if not target:
        # Try to find any linkedin profile in central targets first
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.platform == "linkedin")
        )
        target = await database.fetch_one(query)

    if target:
        decrypted_token = decrypt_token(target['access_token'])
        target_urn = target['target_id']
    else:
        # Fallback to local legacy table
        legacy_query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
        legacy_cred = await database.fetch_one(legacy_query)
        if legacy_cred:
            decrypted_token = legacy_cred['access_token']
            target_urn = legacy_cred['linkedin_urn']

    if decrypted_token:
        await post_to_linkedin(post_id, content, decrypted_token, target_urn, media_url, media_urls)
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
    
    # Store in centralized multi-account tables
    from libs.common.db_models import SocialAccount as CentralSocialAccount, OAuthToken as CentralOAuthToken, SocialTarget as CentralSocialTarget, TokenRefreshMetadata as CentralTokenRefreshMetadata
    from libs.common.security import encrypt_token
    from sqlalchemy import select

    platform_user_id = f"li_{urn}"
    
    # Check if already exists in central social_accounts
    existing_query = select(CentralSocialAccount.c.id).where(
        (CentralSocialAccount.c.user_id == user_id) &
        (CentralSocialAccount.c.platform == "linkedin") &
        (CentralSocialAccount.c.platform_user_id == platform_user_id)
    )
    existing_account = await database.fetch_one(existing_query)
    
    if existing_account:
        account_id = existing_account["id"]
    else:
        account_id = uuid.uuid4()
        await database.execute(
            CentralSocialAccount.insert().values(
                id=account_id,
                user_id=user_id,
                platform="linkedin",
                platform_user_id=platform_user_id,
                account_name="LinkedIn Account"
            )
        )
        
    # Save/Update CentralOAuthToken
    await database.execute(CentralOAuthToken.delete().where(CentralOAuthToken.c.account_id == account_id))
    await database.execute(
        CentralOAuthToken.insert().values(
            id=uuid.uuid4(),
            account_id=account_id,
            access_token=encrypt_token(access_token),
            expires_at=expires_at
        )
    )
    
    # Save/Update CentralTokenRefreshMetadata
    await database.execute(CentralTokenRefreshMetadata.delete().where(CentralTokenRefreshMetadata.c.account_id == account_id))
    await database.execute(
        CentralTokenRefreshMetadata.insert().values(
            id=uuid.uuid4(),
            account_id=account_id,
            refresh_status="success"
        )
    )

    # Write to central targets
    existing_target_query = select(CentralSocialTarget.c.id).where(
        (CentralSocialTarget.c.account_id == account_id) &
        (CentralSocialTarget.c.target_id == urn)
    )
    existing_target = await database.fetch_one(existing_target_query)
    if not existing_target:
        await database.execute(
            CentralSocialTarget.insert().values(
                id=uuid.uuid4(),
                account_id=account_id,
                target_id=urn,
                target_name="LinkedIn Profile",
                target_type="profile",
                access_token=encrypt_token(access_token),
                platform="linkedin"
            )
        )
    
    # return {"status": "connected", "user_id": user_id, "linkedin_urn": urn}
    redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
    return RedirectResponse(url=f"{redirect_url}?connection=success&platform=linkedin")

@app.get("/credentials")
async def get_credentials(user_id: str):
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    if cred:
        return {"connected": True, "platform": "linkedin", "id": str(cred['id'])}
    return {"connected": False, "platform": "linkedin"}

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
