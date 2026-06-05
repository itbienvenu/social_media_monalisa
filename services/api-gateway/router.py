from fastapi import APIRouter, Depends, HTTPException, Request, Header, Response
from fastapi.responses import RedirectResponse, JSONResponse
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

@router.post("/posts/sync")
async def sync_posts_endpoint(
    user_id: str = None,
    user_info: dict = Depends(verify_token)
):
    token_user_id = user_info.get("user_id")
    if user_id and user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    user_id = token_user_id

    async with httpx.AsyncClient() as client:
        try:
             response = await client.post(
                 f"{POST_ORCHESTRATOR_URL}/posts/sync", 
                 params={"user_id": user_id},
                 timeout=20.0 # Sync might take longer
             )
             response.raise_for_status()
             return response.json()
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Service unavailable")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@router.get("/posts")
async def list_posts(
    user_id: str = None,
    user_info: dict = Depends(verify_token)
):
    token_user_id = user_info.get("user_id")
    if user_id and user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    user_id = token_user_id

    async with httpx.AsyncClient() as client:
        try:
             response = await client.get(f"{POST_ORCHESTRATOR_URL}/posts", params={"user_id": user_id})
             response.raise_for_status()
             return response.json()
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Service unavailable")
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


@router.get("/posts/{post_id}/metrics")
async def get_post_metrics(post_id: str, user_info: dict = Depends(verify_token)):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
             response = await client.get(
                 f"{POST_ORCHESTRATOR_URL}/posts/{post_id}/metrics", 
                 params={"user_id": user_id}
             )
             response.raise_for_status()
             return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


@router.get("/posts/{post_id}/logs")
async def get_post_logs(post_id: str, user_info: dict = Depends(verify_token)):
    async with httpx.AsyncClient() as client:
        try:
             response = await client.get(
                 f"{POST_ORCHESTRATOR_URL}/posts/{post_id}/logs"
             )
             response.raise_for_status()
             return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


# --- Connections Management ---

@router.get("/connections")
async def get_connections(
    user_id: str = None,
    user_info: dict = Depends(verify_token)
):
    token_user_id = user_info.get("user_id")
    if user_id and user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    user_id = token_user_id
    services = [
        {"name": "facebook", "url": f"{FACEBOOK_SERVICE_URL}/credentials"},
        {"name": "instagram", "url": "http://instagram-service:8000/credentials"},
        {"name": "linkedin", "url": "http://linkedin-service:8000/credentials"},
        {"name": "tiktok", "url": "http://tiktok-service:8000/credentials"},
    ]
    
    results = []
    async with httpx.AsyncClient() as client:
        # We could run these in parallel with asyncio.gather
        import asyncio
        tasks = []
        for svc in services:
             tasks.append(client.get(svc['url'], params={"user_id": user_id}))
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, resp in enumerate(responses):
            platform = services[i]['name']
            if isinstance(resp, Exception):
                results.append({"platform": platform, "connected": False, "error": str(resp)})
            elif resp.status_code == 200:
                results.append(resp.json())
            else:
                 results.append({"platform": platform, "connected": False})
                 
    return results


@router.delete("/connections/{platform}")
async def delete_connection(platform: str, user_info: dict = Depends(verify_token)):
    user_id = user_info.get("user_id")
    
    if platform == "facebook":
        target_url = f"{FACEBOOK_SERVICE_URL}/credentials"
    elif platform == "tiktok":
        target_url = "http://tiktok-service:8000/credentials"
    elif platform == "instagram":
        target_url = "http://instagram-service:8000/credentials"
    elif platform == "linkedin":
        target_url = "http://linkedin-service:8000/credentials"
    else:
        raise HTTPException(status_code=400, detail="Platform not supported")
        
    async with httpx.AsyncClient() as client:
        try:
             resp = await client.delete(target_url, params={"user_id": user_id})
             resp.raise_for_status()
             return resp.json()
        except httpx.HTTPError as e:
             raise HTTPException(status_code=500, detail=str(e))

@router.get("/facebook/targets")
async def get_facebook_targets(
    user_info: dict = Depends(verify_token)
):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{FACEBOOK_SERVICE_URL}/targets", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

# --- Auth Proxy ---

@router.post("/auth/register")
async def register_proxy(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            body = await request.json()
            resp = await client.post("http://auth-service:8000/register", json=body)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/login")
async def login_proxy(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            body = await request.json()
            resp = await client.post("http://auth-service:8000/login", json=body)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/refresh")
async def refresh_proxy(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            body = await request.json()
            resp = await client.post("http://auth-service:8000/refresh", json=body)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))


# --- Media Proxy ---

@router.post("/media/upload-url")
async def upload_url_proxy(
    request: Request,
    user_info: dict = Depends(verify_token)
):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
            params = dict(request.query_params)
            params["user_id"] = user_id
            resp = await client.post(
                f"{POST_ORCHESTRATOR_URL}/media/upload-url",
                params=params,
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{bucket}/{key:path}")
async def get_upload_proxy(
    bucket: str, 
    key: str,
    user_info: dict = Depends(verify_token)
):
    token_user_id = user_info.get("user_id")
    
    # Enforce user ownership
    key_parts = key.strip("/").split("/")
    if len(key_parts) >= 2 and key_parts[0] == "uploads":
        file_user_id = key_parts[1]
        if file_user_id != token_user_id:
            raise HTTPException(status_code=403, detail="Forbidden: You do not own this resource")
            
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadminpassword"),
            config=boto3.session.Config(signature_version='s3v4')
        )
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        media_type = response.get('ContentType', 'application/octet-stream')
        return Response(content=content, media_type=media_type)
    except ClientError as e:
        status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



FACEBOOK_SERVICE_URL = "http://facebook-service:8000"

@router.post("/auth/{platform}/connect")
async def connect_platform(
    platform: str, 
    user_id: str = None,
    user_info: dict = Depends(verify_token)
):
    token_user_id = user_info.get("user_id")
    if user_id and user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: User ID mismatch")
    user_id = token_user_id

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
             response = await client.get(target_url, params={"code": code, "state": state}, timeout=30.0, follow_redirects=False)
             
             if response.status_code in (301, 302, 307, 308):
                 return RedirectResponse(url=response.headers["location"], status_code=response.status_code)
                 
             response.raise_for_status()
             return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")

from pydantic import BaseModel

class PostUpdatePayload(BaseModel):
    content: str

@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, user_info: dict = Depends(verify_token)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Fetch post to verify ownership/access
            get_resp = await client.get(f"{POST_ORCHESTRATOR_URL}/posts/{post_id}")
            get_resp.raise_for_status()
            
            # 2. Forward delete to post-orchestrator
            response = await client.delete(f"{POST_ORCHESTRATOR_URL}/posts/{post_id}")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@router.put("/posts/{post_id}")
async def update_post(post_id: str, payload: PostUpdatePayload, user_info: dict = Depends(verify_token)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Fetch post to verify ownership/access
            get_resp = await client.get(f"{POST_ORCHESTRATOR_URL}/posts/{post_id}")
            get_resp.raise_for_status()
            
            # 2. Forward put to post-orchestrator
            response = await client.put(
                f"{POST_ORCHESTRATOR_URL}/posts/{post_id}", 
                json=payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
             raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
             raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
