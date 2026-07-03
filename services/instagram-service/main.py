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
    media_urls = message.get("media_urls", [])
    user_id = message.get("user_id")
    if not user_id:
        logger.error("User ID missing in message")
        return
    
    # Fetch Page Token (Target)
    from libs.common.db_models import SocialTarget as CentralSocialTarget, SocialAccount as CentralSocialAccount
    from libs.common.security import decrypt_token
    import sqlalchemy

    instagram_target_id = message.get("instagram_account_id") or message.get("instagram_page_id")
    target = None
    decrypted_token = None
    target_id = None

    if instagram_target_id:
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.target_id == instagram_target_id) &
            (CentralSocialTarget.c.platform == "instagram")
        )
        target = await database.fetch_one(query)

    if not target:
        # Try to find any instagram account in central targets first
        query = sqlalchemy.select(
            CentralSocialTarget.c.target_id,
            CentralSocialTarget.c.access_token
        ).select_from(
            CentralSocialTarget.join(CentralSocialAccount, CentralSocialTarget.c.account_id == CentralSocialAccount.c.id)
        ).where(
            (CentralSocialAccount.c.user_id == user_id) &
            (CentralSocialTarget.c.platform == "instagram")
        )
        target = await database.fetch_one(query)

    if target:
        decrypted_token = decrypt_token(target['access_token'])
        target_id = target['target_id']
    else:
        # Fallback to local legacy table
        legacy_query = SocialTarget.select().where(
            (SocialTarget.c.user_id == user_id) & 
            (SocialTarget.c.platform == "instagram")
        )
        legacy_target = await database.fetch_one(legacy_query)
        if legacy_target:
            decrypted_token = legacy_target['access_token']
            target_id = legacy_target['target_id']

    if decrypted_token:
        await post_to_instagram(post_id, content, decrypted_token, target_id, media_url, media_urls)
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
    
    if os.getenv("MOCK_MODE") == "true" or not FACEBOOK_APP_ID:
        mock_callback_url = f"{base_url}/auth/instagram/callback?code=mock_code&state={user_id}"
        return {"url": mock_callback_url}
        
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
    if os.getenv("MOCK_MODE") == "true" or code == "mock_code":
        user_access_token = f"EAAI_mock_instagram_token_for_{user_id}"
    elif FACEBOOK_APP_ID and FACEBOOK_APP_SECRET:
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
                if os.getenv("MOCK_MODE") == "true":
                    user_access_token = f"EAAI_mock_instagram_token_for_{user_id}"
                else:
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
                
            # Centralized tables
            from libs.common.db_models import SocialAccount as CentralSocialAccount, OAuthToken as CentralOAuthToken, SocialTarget as CentralSocialTarget, TokenRefreshMetadata as CentralTokenRefreshMetadata
            from libs.common.security import encrypt_token
            from sqlalchemy import select

            platform_user_id = f"ig_{ig['id']}"
            
            # Check if already exists in central social_accounts
            existing_query = select(CentralSocialAccount.c.id).where(
                (CentralSocialAccount.c.user_id == user_id) &
                (CentralSocialAccount.c.platform == "instagram") &
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
                        platform="instagram",
                        platform_user_id=platform_user_id,
                        account_name=ig['name']
                    )
                )
                
            # Save/Update CentralOAuthToken
            await database.execute(CentralOAuthToken.delete().where(CentralOAuthToken.c.account_id == account_id))
            await database.execute(
                CentralOAuthToken.insert().values(
                    id=uuid.uuid4(),
                    account_id=account_id,
                    access_token=encrypt_token(user_access_token)
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
                (CentralSocialTarget.c.target_id == ig['id'])
            )
            existing_target = await database.fetch_one(existing_target_query)
            if not existing_target:
                await database.execute(
                    CentralSocialTarget.insert().values(
                        id=uuid.uuid4(),
                        account_id=account_id,
                        target_id=ig['id'],
                        target_name=ig['name'],
                        target_type="instagram_account",
                        access_token=encrypt_token(user_access_token),
                        platform="instagram"
                    )
                )
            
        # return {"status": "connected", "user_id": user_id, "accounts_linked": len(ig_accounts)}
        redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
        return RedirectResponse(url=f"{redirect_url}?connection=success&platform=instagram")
            
    except Exception as e:
        logger.error(f"Failed to fetch IG accounts: {e}")
        redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
        return RedirectResponse(url=f"{redirect_url}?connection=error&platform=instagram&reason=fetch_failed")
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

@app.get("/feed")
async def get_feed(user_id: str):
    """
    Fetches posts from the connected Instagram account.
    """
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.platform == "instagram")
    ).limit(1)
    target = await database.fetch_one(query)
    
    if not target:
        return []
        
    client = InstagramClient(target['access_token'], target['target_id'])
    try:
        posts = await client.get_instagram_posts()
        
        normalized_posts = []
        for p in posts:
            normalized_posts.append({
                "original_id": p['id'],
                "content": p.get('caption', ''),
                "created_at": p.get('timestamp'),
                "platform": "instagram",
                "permalink": p.get('permalink')
            })
        return normalized_posts
    except Exception as e:
        logger.error(f"Error fetching Instagram feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@app.get("/posts/{platform_post_id}/metrics")
async def get_instagram_post_metrics(platform_post_id: str, user_id: str):
    """
    Fetches metrics (likes, comments, permalink) for a specific Instagram post.
    """
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.platform == "instagram")
    )
    target = await database.fetch_one(query)
    if not target:
        raise HTTPException(status_code=400, detail="Instagram credentials not found for this user")
        
    client = InstagramClient(target['access_token'], target['target_id'])
    try:
        metrics = await client.get_post_metrics(platform_post_id)
        return metrics
    except Exception as e:
        logger.error(f"Error fetching Instagram metrics for {platform_post_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@app.delete("/posts/{platform_post_id}")
async def delete_instagram_post(platform_post_id: str, user_id: str):
    """
    Deletes an Instagram post from local reference. Note that the Instagram Graph API
    does not support deleting media via the API, so it must be deleted manually on Instagram.
    """
    logger.warning(
        f"Instagram Graph API does not support deleting media via the API. "
        f"Removing local reference for post ID {platform_post_id} from dashboard."
    )
    return {
        "status": "success", 
        "deleted": True, 
        "info": "Instagram Graph API does not support deleting media. Please delete manually on Instagram."
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
