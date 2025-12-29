from fastapi import APIRouter, Depends, HTTPException, Request
from libs.common.auth import verify_token
from libs.common.serializers import PostCreate, PostResponse
import httpx
import os

router = APIRouter()

POST_ORCHESTRATOR_URL = "http://post-orchestrator:8000"

@router.post("/posts", response_model=PostResponse)
async def create_post(
    post: PostCreate, 
    user_info: dict = Depends(verify_token)
):
    """
    Proxy to post-orchestrator to create a post.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Forward the request to post-orchestrator
            user_id = user_info.get("user_id", "anonymous")
            response = await client.post(
                f"{POST_ORCHESTRATOR_URL}/posts",
                json=post.model_dump(),
                params={"user_id": user_id},
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@router.get("/posts/{post_id}")
async def get_post(post_id: str, user_info: dict = Depends(verify_token)):
    async with httpx.AsyncClient() as client:
        try:
             response = await client.get(f"{POST_ORCHESTRATOR_URL}/posts/{post_id}")
             response.raise_for_status()
             return response.json()
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Service unavailable")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


# --- Auth Proxy ---

FACEBOOK_SERVICE_URL = "http://facebook-service:8000"

@router.post("/auth/{platform}/connect")
async def connect_platform(platform: str, user_id: str):
    # Proxy to the specific platform service
    # In a real app, we'd have a service registry or switch case.
    if platform == "facebook":
        target_url = f"{FACEBOOK_SERVICE_URL}/auth/connect"
    elif platform == "tiktok":
        target_url = "http://tiktok-service:8000/auth/connect"
    elif platform == "instagram":
        target_url = "http://instagram-service:8000/auth/connect"
    elif platform == "linkedin":
        target_url = "http://linkedin-service:8000/auth/connect"
    else:
        raise HTTPException(status_code=400, detail="Platform not supported")

    async with httpx.AsyncClient() as client:
        try:
             # We pass the user_id as a query param to the service
             response = await client.post(target_url, params={"user_id": user_id})
             response.raise_for_status()
             return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")

@router.get("/auth/{platform}/callback")
async def platform_callback(platform: str, code: str, state: str):
    if platform == "facebook":
        target_url = f"{FACEBOOK_SERVICE_URL}/auth/callback"
    elif platform == "tiktok":
        target_url = "http://tiktok-service:8000/auth/callback"
    elif platform == "instagram":
        target_url = "http://instagram-service:8000/auth/callback"
    elif platform == "linkedin":
        target_url = "http://linkedin-service:8000/auth/callback"
    else:
        raise HTTPException(status_code=400, detail="Platform not supported")
        
    async with httpx.AsyncClient() as client:
        try:
             response = await client.get(target_url, params={"code": code, "state": state})
             response.raise_for_status()
             return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
