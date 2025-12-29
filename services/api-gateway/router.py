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
            response = await client.post(
                f"{POST_ORCHESTRATOR_URL}/posts",
                json=post.model_dump(),
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

