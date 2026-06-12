from fastapi import APIRouter, Depends, HTTPException, Request, Header, Response
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from libs.common.auth import verify_token
from libs.common.serializers import PostCreate, PostResponse
import httpx
import os

router = APIRouter()

POST_ORCHESTRATOR_URL = "http://post-orchestrator:8000"
AUTH_SERVICE_URL = "http://auth-service:8000"


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
                timeout=30.0
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


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user_info: dict = Depends(verify_token)):
    """Get the status of a background media processing job."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{POST_ORCHESTRATOR_URL}/jobs/{job_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)


@router.post("/auth/logout")
async def logout(response: Response):
    """Logout user by clearing auth cookies."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/logout"
            )
            resp.raise_for_status()
            res = JSONResponse(content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                res.headers.append("set-cookie", cookie)
            return res
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
            resp = await client.post(f"{AUTH_SERVICE_URL}/register", json=body)
            res = JSONResponse(status_code=resp.status_code, content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                res.headers.append("set-cookie", cookie)
            return res
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/login")
async def login_proxy(request: Request, response: Response):
    async with httpx.AsyncClient() as client:
        try:
            body = await request.json()
            resp = await client.post(f"{AUTH_SERVICE_URL}/login", json=body)
            res = JSONResponse(status_code=resp.status_code, content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                res.headers.append("set-cookie", cookie)
            return res
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/refresh")
async def refresh_proxy(request: Request, response: Response):
    async with httpx.AsyncClient() as client:
        try:
            body = await request.json()
            # Forward the incoming cookies (which contain the refresh token)
            headers = {}
            cookie_header = request.headers.get("cookie")
            if cookie_header:
                headers["cookie"] = cookie_header

            resp = await client.post(f"{AUTH_SERVICE_URL}/refresh", json=body, headers=headers)
            res = JSONResponse(status_code=resp.status_code, content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                res.headers.append("set-cookie", cookie)
            return res
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/google/url")
async def get_google_auth_url(response: Response):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/auth/google/url")
            resp.raise_for_status()
            
            # Forward Set-Cookie headers (which contains the oauth_state cookie)
            json_resp = JSONResponse(content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                json_resp.headers.append("set-cookie", cookie)
            return json_resp
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/google/callback")
async def google_callback(code: str, state: str, request: Request, response: Response):
    host = request.headers.get("host", "")
    if "localhost" not in host and "127.0.0.1" not in host:
        local_url = str(request.url).replace(f"https://{host}", "http://localhost:8000").replace(f"http://{host}", "http://localhost:8000")
        return RedirectResponse(url=local_url)

    async with httpx.AsyncClient() as client:
        try:
            # Forward the incoming cookies (which contain oauth_state)
            headers = {}
            cookie_header = request.headers.get("cookie")
            if cookie_header:
                headers["cookie"] = cookie_header

            resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/google/callback",
                params={"code": code, "state": state},
                headers=headers,
                follow_redirects=False
            )
            
            if resp.status_code in (301, 302, 307, 308):
                redirect_resp = RedirectResponse(url=resp.headers["location"], status_code=resp.status_code)
                for cookie in resp.headers.get_list("set-cookie"):
                    redirect_resp.headers.append("set-cookie", cookie)
                return redirect_resp

            resp.raise_for_status()
            json_resp = JSONResponse(content=resp.json())
            for cookie in resp.headers.get_list("set-cookie"):
                json_resp.headers.append("set-cookie", cookie)
            return json_resp
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
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
    request: Request
):
    # Public endpoint to allow external social media platforms (Facebook, Instagram, etc.) to fetch the media files
    
    # Restrict bucket to configured uploads bucket only
    ALLOWED_BUCKETS = {
        os.getenv("MINIO_BUCKET_NAME", "uploads"),
        os.getenv("S3_BUCKET_NAME", "uploads"),
        "uploads",
        "social-media-uploads"
    }
    if bucket not in ALLOWED_BUCKETS:
        raise HTTPException(status_code=403, detail="Access denied: invalid bucket")

    # Restrict key to safe prefix
    if not key.startswith("uploads/"):
        raise HTTPException(status_code=403, detail="Access denied: invalid key prefix")

    # Verify signature and expiration
    from libs.common.signatures import verify_url_path
    
    exp_val = request.query_params.get("exp")
    sig = request.query_params.get("sig")
    
    if not exp_val or not sig:
        raise HTTPException(status_code=403, detail="Access denied: missing signature parameters")
        
    if not verify_url_path(bucket, key, exp_val, sig):
        raise HTTPException(status_code=403, detail="Access denied: invalid or expired signature")

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
        
        # Support Range requests
        params = {"Bucket": bucket, "Key": key}
        range_header = request.headers.get("range")
        if range_header:
            params["Range"] = range_header
            
        response_s3 = s3_client.get_object(**params)
        media_type = response_s3.get('ContentType', 'application/octet-stream')
        
        # Build headers
        res_headers = {
            "Accept-Ranges": "bytes"
        }
        if "ContentRange" in response_s3:
            res_headers["Content-Range"] = response_s3["ContentRange"]
        if "ContentLength" in response_s3:
            res_headers["Content-Length"] = str(response_s3["ContentLength"])
        if "ETag" in response_s3:
            res_headers["ETag"] = response_s3["ETag"]
        if "LastModified" in response_s3:
            res_headers["Last-Modified"] = response_s3["LastModified"].strftime("%a, %d %b %Y %H:%M:%S GMT")
            
        status_code = 206 if range_header else 200
        
        def chunk_generator(body):
            for chunk in body.iter_chunks(chunk_size=65536):
                yield chunk
                
        return StreamingResponse(
            chunk_generator(response_s3['Body']),
            status_code=status_code,
            headers=res_headers,
            media_type=media_type
        )
    except ClientError as e:
        status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Notifications Proxy ---

@router.get("/notifications")
async def get_notifications(
    user_info: dict = Depends(verify_token)
):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{POST_ORCHESTRATOR_URL}/notifications",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_info: dict = Depends(verify_token)
):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{POST_ORCHESTRATOR_URL}/notifications/{notification_id}/read",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    user_info: dict = Depends(verify_token)
):
    user_id = user_info.get("user_id")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{POST_ORCHESTRATOR_URL}/notifications/read-all",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except httpx.HTTPError as e:
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
                 redirect_resp = RedirectResponse(url=response.headers["location"], status_code=response.status_code)
                 for cookie in response.headers.get_list("set-cookie"):
                     redirect_resp.headers.append("set-cookie", cookie)
                 return redirect_resp
                 
             response.raise_for_status()
             json_resp = JSONResponse(content=response.json())
             for cookie in response.headers.get_list("set-cookie"):
                 json_resp.headers.append("set-cookie", cookie)
             return json_resp
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
