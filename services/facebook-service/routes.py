import os
import uuid
import logging
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from services.facebook_service.db import database, SocialCredential, SocialTarget
from services.facebook_service.logic import FacebookClient
from services.facebook_service.schemas import (
    ConnectResponse,
    CredentialResponse,
    DeleteCredentialsResponse,
    FacebookPostResponse,
    FacebookMetricsResponse,
)

logger = logging.getLogger("facebook-service")

router = APIRouter()

@router.post("/auth/connect", response_model=ConnectResponse)
async def connect_facebook(user_id: str):
    """
    Returns the Facebook OAuth URL.
    """
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{base_url}/auth/facebook/callback"
    
    if os.getenv("MOCK_MODE") == "true" or not FACEBOOK_APP_ID:
        # Return direct local redirect to callback to auto-mock connection
        mock_callback_url = f"{base_url}/auth/facebook/callback?code=mock_code&state={user_id}"
        return ConnectResponse(url=mock_callback_url)
        
    # Scopes for Page Management
    SCOPES = "pages_show_list,pages_read_engagement,pages_manage_posts,pages_manage_metadata"
    
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={FACEBOOK_APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"state={user_id}&"
        f"scope={SCOPES}"
    )
    
    return ConnectResponse(url=auth_url)

@router.get("/auth/callback")
async def facebook_callback(code: str, state: str):
    """
    Receives code, exchanges for token, fetches Pages, stores everything.
    """
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
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        params = {
            "client_id": FACEBOOK_APP_ID,
            "redirect_uri": f"{base_url}/auth/facebook/callback",
            "client_secret": FACEBOOK_APP_SECRET,
            "code": code
        }

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Exchanging code for token at {token_url} with redirect_uri={params['redirect_uri']}")
                resp = await client.get(token_url, params=params)
                resp.raise_for_status()
                user_access_token = resp.json().get("access_token")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Status Error: {e.response.status_code} - {e.response.text}")
                return {
                    "status": "error", 
                    "reason": "auth_exchange_failed", 
                    "details": f"Status: {e.response.status_code}, Body: {e.response.text}"
                }
            except Exception as e:
                import traceback
                logger.error(f"Failed to exchange token with Facebook: {e}")
                logger.error(traceback.format_exc())
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
    
    redirect_url = os.getenv("LOGIN_REDIRECT_URL", "http://localhost:3000/dashboard")
    return RedirectResponse(url=redirect_url)

@router.get("/credentials", response_model=CredentialResponse)
async def get_credentials(user_id: str):
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    if cred:
        return CredentialResponse(connected=True, platform="facebook", id=str(cred['id']))
    return CredentialResponse(connected=False, platform="facebook")

@router.delete("/credentials", response_model=DeleteCredentialsResponse)
async def delete_credentials(user_id: str):
    query = SocialCredential.delete().where(SocialCredential.c.user_id == user_id)
    await database.execute(query)
    # Also delete targets
    t_query = SocialTarget.delete().where(SocialTarget.c.user_id == user_id)
    await database.execute(t_query)
    return DeleteCredentialsResponse(status="deleted")

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/targets")
async def get_targets(user_id: str):
    """
    Returns the list of stored targets (Pages/Groups) for this user.
    """
    query = SocialTarget.select().where(SocialTarget.c.user_id == user_id)
    targets = await database.fetch_all(query)
    return [
        {
            "target_id": t["target_id"],
            "target_name": t["target_name"],
            "target_type": t["target_type"],
            "platform": t["platform"]
        }
        for t in targets
    ]

@router.get("/feed", response_model=list[FacebookPostResponse])
async def get_feed(user_id: str):
    """
    Fetches posts from the connected Facebook Page(s).
    """
    # 1. Get stored targets (Pages)
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.target_type == "page")
    ).limit(1) # Just get the first one for now
    
    target = await database.fetch_one(query)
    
    if not target:
        # If no target, return empty list
        return []
    
    # 2. Fetch posts
    client = FacebookClient(target['access_token'], target['target_id'])
    try:
        posts = await client.get_page_posts(target['target_id'], target['access_token'])
        
        # Normalize response
        normalized_posts = []
        for p in posts:
            if 'message' in p: # Only sync posts with text content for now?
                normalized_posts.append(
                    FacebookPostResponse(
                        original_id=p['id'],
                        content=p.get('message', ''),
                        created_at=p.get('created_time'),
                        platform="facebook",
                        permalink=p.get('permalink_url')
                    )
                )
        return normalized_posts
    except Exception as e:
        logger.error(f"Error fetching feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@router.get("/posts/{platform_post_id}/metrics", response_model=FacebookMetricsResponse)
async def get_facebook_post_metrics(platform_post_id: str, user_id: str):
    """
    Fetches engagement metrics for a specific Facebook post.
    """
    # 1. Get stored targets (Pages)
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.target_type == "page")
    ).limit(1)
    target = await database.fetch_one(query)
    
    if not target:
        raise HTTPException(status_code=404, detail="No connected Page target found for metrics query")
        
    client = FacebookClient(target['access_token'], target['target_id'])
    try:
        metrics = await client.get_post_metrics(platform_post_id)
        return FacebookMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Error fetching metrics for {platform_post_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@router.delete("/posts/{platform_post_id}")
async def delete_facebook_post(platform_post_id: str, user_id: str):
    """
    Deletes a specific post from the Facebook Page.
    """
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.target_type == "page")
    ).limit(1)
    target = await database.fetch_one(query)
    
    if not target:
        raise HTTPException(status_code=404, detail="No connected Page target found to delete post")
        
    client = FacebookClient(target['access_token'], target['target_id'])
    try:
        success = await client.delete_post(platform_post_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error deleting Facebook post {platform_post_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@router.put("/posts/{platform_post_id}")
async def update_facebook_post(platform_post_id: str, user_id: str, message: str):
    """
    Updates the message/caption of a specific post on Facebook Page.
    """
    query = SocialTarget.select().where(
        (SocialTarget.c.user_id == user_id) & 
        (SocialTarget.c.target_type == "page")
    ).limit(1)
    target = await database.fetch_one(query)
    
    if not target:
        raise HTTPException(status_code=404, detail="No connected Page target found to update post")
        
    client = FacebookClient(target['access_token'], target['target_id'])
    try:
        success = await client.update_post(platform_post_id, message)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error updating Facebook post {platform_post_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()
