from fastapi import FastAPI, UploadFile, File, HTTPException
from libs.common.serializers import PostCreate, PostResponse, PostStatus, Platform
from services.post_orchestrator.db import database, Post, PostTarget, PostLog, metadata
import sqlalchemy
import asyncio
from services.post_orchestrator.media import generate_upload_url, delete_media_files, get_presigned_download_url
from services.post_orchestrator.events import publish_post_event, mq
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import json
import logging
from libs.common.db import connect_db_with_retry
from libs.common.logger import log_post_stage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("post-orchestrator")

async def handle_post_success(data: dict, platform: str):
    post_id = data.get("post_id")
    platform_post_id = data.get("platform_post_id")
    cdn_urls = data.get("cdn_urls") or []
    
    logger.info(f"Received success event for post {post_id} on platform {platform}. CDN URLs count: {len(cdn_urls)}")
    await log_post_stage(
        database, post_id, "orchestrator", "platform_success", "INFO",
        f"Platform '{platform}' posted successfully. External ID: {platform_post_id}"
    )
    try:
        post_uuid = uuid.UUID(post_id)
        
        # 1. Update matching target status
        target_query = PostTarget.update().where(
            PostTarget.c.post_id == post_uuid,
            PostTarget.c.platform == platform
        ).values(
            status="published",
            external_id=platform_post_id
        )
        await database.execute(target_query)

        # 2. Get current local media_keys for cleanup and swap with CDN URLs
        import json
        
        post_query = Post.select().where(Post.c.id == post_uuid)
        existing_post = await database.fetch_one(post_query)
        
        original_keys = []
        if existing_post and existing_post["media_keys"]:
            try:
                original_keys = json.loads(existing_post["media_keys"])
            except Exception:
                original_keys = [existing_post["media_keys"]]
        
        # Update main post status to published and swap media keys if CDN URLs exist
        update_vals = {
            "status": PostStatus.PUBLISHED.value,
            "updated_at": datetime.utcnow()
        }
        
        if cdn_urls:
            update_vals["media_key"] = cdn_urls[0]
            update_vals["media_keys"] = json.dumps(cdn_urls)
            
        query = Post.update().where(Post.c.id == post_uuid).values(**update_vals)
        await database.execute(query)
        logger.info(f"Successfully updated post {post_id} target ({platform}) to PUBLISHED in DB")
        
        # 3. Clean up the original local MinIO files since Facebook has copied them to its CDN
        if cdn_urls and original_keys:
            local_keys_to_delete = [
                k for k in original_keys
                if isinstance(k, str) and (k.startswith("uploads/") or "/uploads/" in k)
            ]
            if local_keys_to_delete:
                # Run cleanup in a separate thread/background task to avoid blocking the listener loop
                loop = asyncio.get_running_loop()
                fut = loop.run_in_executor(None, delete_media_files, local_keys_to_delete)
                
                def cleanup_done_callback(f):
                    try:
                        f.result()
                    except Exception as cleanup_err:
                        logger.error(f"Failed to delete media files during background cleanup for post {post_id}: {cleanup_err}")
                
                fut.add_done_callback(cleanup_done_callback)
                logger.info(f"Triggered background cleanup of {len(local_keys_to_delete)} local MinIO files for post {post_id}")
            
    except Exception as e:
        logger.error(f"Failed to update post success in DB: {e}")

async def handle_post_failed(data: dict, platform: str):
    post_id = data.get("post_id")
    reason = data.get("reason", "unknown error")
    logger.info(f"Received failed event for post {post_id} on platform {platform} due to: {reason}")
    await log_post_stage(
        database, post_id, "orchestrator", "platform_failed", "ERROR",
        f"Platform '{platform}' posting failed. Reason: {reason}"
    )
    try:
        post_uuid = uuid.UUID(post_id)
        
        # 1. Update matching target status
        target_query = PostTarget.update().where(
            PostTarget.c.post_id == post_uuid,
            PostTarget.c.platform == platform
        ).values(
            status="failed"
        )
        await database.execute(target_query)

        # 2. Check if ALL targets for this post have failed
        # If all have failed, set the main post status to failed
        all_targets_query = PostTarget.select().where(PostTarget.c.post_id == post_uuid)
        targets = await database.fetch_all(all_targets_query)
        statuses = [t["status"] for t in targets]
        if all(s == "failed" for s in statuses):
            query = Post.update().where(Post.c.id == post_uuid).values(
                status=PostStatus.FAILED.value,
                updated_at=datetime.utcnow()
            )
            await database.execute(query)
            logger.info(f"Successfully updated main post {post_id} to FAILED in DB (all targets failed)")
        else:
            # If at least one target succeeded, main post status might be published
            if any(s == "published" for s in statuses):
                query = Post.update().where(Post.c.id == post_uuid).values(
                    status=PostStatus.PUBLISHED.value,
                    updated_at=datetime.utcnow()
                )
                await database.execute(query)
            logger.info(f"Updated post target {platform} to FAILED for post {post_id}")
    except Exception as e:
        logger.error(f"Failed to update post failure in DB: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db_with_retry(database)
    
    # Create tables (for simplicity in this monorepo setup)
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
    except Exception as e:
        logger.warning(f"Table creation skipped or already completed: {e}")
    
    # Run dynamic schema migrations for pre-existing tables
    with engine.begin() as conn:
        try:
            inspector = sqlalchemy.inspect(engine)
            if "posts" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("posts")]
                if "external_id" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN external_id VARCHAR"))
                    logger.info("Migrated schema: Added column external_id to posts table")
                if "platform" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN platform VARCHAR"))
                    logger.info("Migrated schema: Added column platform to posts table")
                if "media_keys" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN media_keys VARCHAR"))
                    logger.info("Migrated schema: Added column media_keys to posts table")
                if "is_reel" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN is_reel BOOLEAN DEFAULT FALSE"))
                    logger.info("Migrated schema: Added column is_reel to posts table")
                
                # Check and add unique constraint
                # uq_user_platform_external_post unique constraint
                # Check for existing constraint in postgres
                has_constraint = False
                if "postgresql" in str(database.url):
                    result = conn.execute(sqlalchemy.text(
                        "SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_platform_external_post'"
                    )).fetchone()
                    has_constraint = result is not None
                
                if not has_constraint:
                    try:
                        conn.execute(sqlalchemy.text(
                            "ALTER TABLE posts ADD CONSTRAINT uq_user_platform_external_post UNIQUE (user_id, platform, external_id)"
                        ))
                        logger.info("Migrated schema: Added unique constraint uq_user_platform_external_post to posts table")
                    except Exception as ce:
                        logger.warning(f"Could not add unique constraint to posts table: {ce}")
        except Exception as me:
            logger.error(f"Failed to check/migrate posts table schema: {me}")
    
    # Start RabbitMQ subscriptions in background task with retry
    async def setup_subscriptions_loop():
        logger.info("Starting RabbitMQ subscription setup loop in post-orchestrator...")
        while True:
            try:
                await mq.connect()
                
                def make_success_handler(platform_name: str):
                    async def handler(data: dict):
                        p_name = data.get("platform", platform_name)
                        await handle_post_success(data, p_name)
                    return handler

                def make_failed_handler(platform_name: str):
                    async def handler(data: dict):
                        p_name = data.get("platform", platform_name)
                        await handle_post_failed(data, p_name)
                    return handler

                for platform in ["facebook", "tiktok", "linkedin", "instagram"]:
                    await mq.subscribe(f"posts.{platform}.success", make_success_handler(platform))
                    await mq.subscribe(f"posts.{platform}.failed", make_failed_handler(platform))
                logger.info("Successfully subscribed to posts success and failure events in post-orchestrator")
                break
            except Exception as e:
                logger.error(f"Failed to setup RabbitMQ subscriptions in post-orchestrator: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    consume_task = asyncio.create_task(setup_subscriptions_loop())
        
    yield
    
    consume_task.cancel()
    try:
        await mq.disconnect()
    except Exception:
        pass
    await database.disconnect()

app = FastAPI(title="Post Orchestrator", lifespan=lifespan)

@app.post("/posts", response_model=PostResponse)
async def create_post(post_data: PostCreate, user_id: str):
    import json
    
    media_key = post_data.media_key
    media_keys = post_data.media_keys
    if not media_key and media_keys:
        media_key = media_keys[0]
    if not media_keys and media_key:
        media_keys = [media_key]
        
    # 1. Store in DB
    query = Post.insert().values(
        id=uuid.uuid4(),
        content=post_data.content,
        media_key=media_key,
        media_keys=json.dumps(media_keys) if media_keys else None,
        is_reel=post_data.is_reel,
        status=PostStatus.PENDING.value,
        user_id=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    ).returning(Post)
    
    post = await database.fetch_one(query)
    
    await log_post_stage(
        database, post['id'], "orchestrator", "post_created", "INFO",
        f"Post created in database. Targets: {[p.value if hasattr(p, 'value') else str(p) for p in post_data.platforms]}"
    )
    
    # 2. Store Metadata (Targets)
    for platform in post_data.platforms:
        target_query = PostTarget.insert().values(
            id=uuid.uuid4(),
            post_id=post['id'],
            platform=platform.value if hasattr(platform, "value") else str(platform),
            status="pending"
        )
        await database.execute(target_query)
        
    # 3. Publish Events
    failed_platforms = []
    for platform in post_data.platforms:
        platform_str = platform.value if hasattr(platform, "value") else str(platform)
        try:
            await publish_post_event(
                post_id=post['id'], 
                platform=platform, 
                content=post_data.content, 
                media_key=post_data.media_key, 
                user_id=user_id,
                media_keys=post_data.media_keys,
                is_reel=post_data.is_reel,
                facebook_page_id=post_data.facebook_page_id
            )
            # Only emit event_published lifecycle stage after confirmed publish success
            await log_post_stage(
                database, post['id'], "orchestrator", "event_published", "INFO",
                f"Successfully published post event to posts.{platform_str}"
            )
        except Exception as e:
            failed_platforms.append((platform_str, str(e)))
            
    if failed_platforms:
        # Roll back database changes for this post
        try:
            await database.execute(PostTarget.delete().where(PostTarget.c.post_id == post['id']))
            await database.execute(PostLog.delete().where(PostLog.c.post_id == post['id']))
            await database.execute(Post.delete().where(Post.c.id == post['id']))
        except Exception as rollback_err:
            logger.error(f"Rollback failed: {rollback_err}")
            
        error_details = ", ".join([f"{p}: {err}" for p, err in failed_platforms])
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish post event, rolling back: {error_details}"
        )

    return PostResponse(
        id=post['id'],
        content=post['content'],
        media_key=get_presigned_download_url(post['media_key']),
        media_keys=[get_presigned_download_url(k) for k in json.loads(post['media_keys'])] if post['media_keys'] else None,
        platforms=post_data.platforms,
        is_reel=post['is_reel'],
        status=PostStatus(post['status']),
        created_at=post['created_at'],
        updated_at=post['updated_at']
    )

from pydantic import BaseModel

class PostUpdate(BaseModel):
    content: str

@app.delete("/posts/{post_id}")
async def delete_post(post_id: uuid.UUID):
    import httpx
    # 1. Fetch the post to make sure it exists and to get media keys for cleanup
    post_query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(post_query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    user_id = post["user_id"]

    # 2. Fetch all post targets
    targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
    targets = await database.fetch_all(targets_query)
    
    # 3. Delete from the respective platform service for targets that were published
    async with httpx.AsyncClient() as client:
        for target in targets:
            platform = target["platform"]
            ext_id = target["external_id"]
            if ext_id and target["status"] in ("published", "success", "completed", "synced"):
                svc_url = f"http://{platform}-service:8000/posts/{ext_id}"
                try:
                    logger.info(f"Deleting post {ext_id} from platform {platform}")
                    resp = await client.delete(svc_url, params={"user_id": user_id}, timeout=10.0)
                    if resp.status_code != 200:
                        logger.error(f"Platform service {platform} failed to delete post {ext_id}: {resp.text}")
                except Exception as e:
                    logger.error(f"Failed to connect to platform service {platform} to delete post {ext_id}: {e}")

        # Also handle historically synced posts
        if post["status"] == PostStatus.SYNCED.value and post["external_id"] and post["platform"]:
            platform = post["platform"]
            ext_id = post["external_id"]
            svc_url = f"http://{platform}-service:8000/posts/{ext_id}"
            try:
                logger.info(f"Deleting synced post {ext_id} from platform {platform}")
                resp = await client.delete(svc_url, params={"user_id": user_id}, timeout=10.0)
                if resp.status_code != 200:
                    logger.error(f"Platform service {platform} failed to delete synced post {ext_id}: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to connect to platform service {platform} to delete synced post {ext_id}: {e}")

    # 4. Clean up local MinIO/S3 media files if any
    try:
        media_keys_list = json.loads(post["media_keys"]) if post["media_keys"] else []
        if post["media_key"] and post["media_key"] not in media_keys_list:
            media_keys_list.append(post["media_key"])
        if media_keys_list:
            logger.info(f"Deleting local media files from MinIO: {media_keys_list}")
            # Strip pre-signed parts or URL prefixes if they are stored as full URLs
            clean_keys = []
            for key in media_keys_list:
                # If key is a full URL, extract the path after '/uploads/'
                if "http" in key:
                    parts = key.split("/uploads/")
                    if len(parts) > 1:
                        # Re-add prefix or keep it relative
                        clean_keys.append("uploads/" + parts[1])
                    else:
                        clean_keys.append(key)
                else:
                    clean_keys.append(key)
            # Run in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, delete_media_files, clean_keys)
    except Exception as media_err:
        logger.error(f"Failed to clean up MinIO files for post {post_id}: {media_err}")

    # 5. Delete from database (targets, logs, then post)
    await database.execute(PostTarget.delete().where(PostTarget.c.post_id == post_id))
    await database.execute(PostLog.delete().where(PostLog.c.post_id == post_id))
    await database.execute(Post.delete().where(Post.c.id == post_id))

    return {"status": "deleted"}

@app.put("/posts/{post_id}", response_model=PostResponse)
async def update_post_endpoint(post_id: uuid.UUID, update_data: PostUpdate):
    import httpx
    # 1. Fetch post
    post_query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(post_query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    user_id = post["user_id"]

    # 2. Fetch targets
    targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
    targets = await database.fetch_all(targets_query)

    # 3. Update the post message/caption on each platform
    async with httpx.AsyncClient() as client:
        for target in targets:
            platform = target["platform"]
            ext_id = target["external_id"]
            if ext_id and target["status"] in ("published", "success", "completed", "synced"):
                svc_url = f"http://{platform}-service:8000/posts/{ext_id}"
                try:
                    logger.info(f"Updating post {ext_id} message on platform {platform}")
                    resp = await client.put(
                        svc_url, 
                        params={"user_id": user_id, "message": update_data.content}, 
                        timeout=10.0
                    )
                    if resp.status_code != 200:
                        logger.error(f"Platform service {platform} failed to update post {ext_id}: {resp.text}")
                except Exception as e:
                    logger.error(f"Failed to connect to platform service {platform} to update post {ext_id}: {e}")

        # Historically synced post
        if post["status"] == PostStatus.SYNCED.value and post["external_id"] and post["platform"]:
            platform = post["platform"]
            ext_id = post["external_id"]
            svc_url = f"http://{platform}-service:8000/posts/{ext_id}"
            try:
                logger.info(f"Updating synced post {ext_id} message on platform {platform}")
                resp = await client.put(
                    svc_url, 
                    params={"user_id": user_id, "message": update_data.content}, 
                    timeout=10.0
                )
                if resp.status_code != 200:
                    logger.error(f"Platform service {platform} failed to update synced post {ext_id}: {resp.text}")
            except Exception as e:
                logger.error(f"Failed to connect to platform service {platform} to update synced post {ext_id}: {e}")

    # 4. Update local database
    update_query = (
        Post.update()
        .where(Post.c.id == post_id)
        .values(content=update_data.content, updated_at=datetime.utcnow())
    )
    await database.execute(update_query)

    # 5. Fetch updated post to return
    updated_post = await database.fetch_one(post_query)
    
    # Get platforms list
    platforms_list = [Platform(t["platform"]) for t in targets if t["platform"] in Platform.__members__.values()]
    if not platforms_list:
        platforms_list = [Platform.FACEBOOK] # Fallback default
        
    return PostResponse(
        id=updated_post['id'],
        content=updated_post['content'],
        media_key=get_presigned_download_url(updated_post['media_key']),
        media_keys=[get_presigned_download_url(k) for k in json.loads(updated_post['media_keys'])] if updated_post['media_keys'] else None,
        platforms=platforms_list,
        is_reel=updated_post['is_reel'],
        status=PostStatus(updated_post['status']),
        created_at=updated_post['created_at'],
        updated_at=updated_post['updated_at']
    )

@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: uuid.UUID):
    query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
    targets = await database.fetch_all(targets_query)
    platforms = []
    for t in targets:
        try:
            platforms.append(Platform(t["platform"]))
        except ValueError:
            pass
    if not platforms and post["platform"]:
        try:
            platforms.append(Platform(post["platform"]))
        except ValueError:
            pass
    if not platforms:
        platforms = [Platform.FACEBOOK]
        
    return PostResponse(
        id=post['id'],
        content=post['content'],
        media_key=get_presigned_download_url(post['media_key']),
        media_keys=[get_presigned_download_url(k) for k in json.loads(post['media_keys'])] if post['media_keys'] else None,
        platforms=platforms,
        is_reel=post['is_reel'],
        status=PostStatus(post['status']),
        created_at=post['created_at'],
        updated_at=post['updated_at']
    )

@app.get("/posts/{post_id}/logs")
async def get_post_logs(post_id: uuid.UUID):
    query = """
        SELECT id, post_id, platform, stage, status, message, created_at
        FROM post_logs
        WHERE post_id = :post_id
        ORDER BY created_at ASC
    """
    logs = await database.fetch_all(query=query, values={"post_id": post_id})
    return [
        {
            "id": str(log["id"]),
            "post_id": str(log["post_id"]),
            "platform": log["platform"],
            "stage": log["stage"],
            "status": log["status"],
            "message": log["message"],
            "created_at": log["created_at"].isoformat() if log["created_at"] else None
        }
        for log in logs
    ]

@app.get("/posts", response_model=list[PostResponse])
async def list_posts(user_id: str):
    query = Post.select().where(Post.c.user_id == user_id).order_by(Post.c.created_at.desc())
    posts = await database.fetch_all(query)
    
    if not posts:
        return []
        
    post_ids = [p['id'] for p in posts]
    targets_query = PostTarget.select().where(PostTarget.c.post_id.in_(post_ids))
    targets = await database.fetch_all(targets_query)
    
    from collections import defaultdict
    post_platforms = defaultdict(list)
    for t in targets:
        try:
            post_platforms[t["post_id"]].append(Platform(t["platform"]))
        except ValueError:
            pass
            
    import json
    results = []
    for p in posts:
        platforms = post_platforms[p['id']]
        if not platforms:
            if p['platform']:
                try:
                    platforms = [Platform(p['platform'])]
                except ValueError:
                    platforms = [Platform.FACEBOOK]
            else:
                platforms = [Platform.FACEBOOK]
        results.append(PostResponse(
            id=p['id'],
            content=p['content'],
            media_key=get_presigned_download_url(p['media_key']),
            media_keys=[get_presigned_download_url(k) for k in json.loads(p['media_keys'])] if p['media_keys'] else None,
            platforms=platforms,
            is_reel=p['is_reel'],
            status=PostStatus(p['status']),
            created_at=p['created_at'],
            updated_at=p['updated_at']
        ))
    return results

@app.post("/media/upload-url")
async def get_upload_url(filename: str, user_id: str, content_type: str = "image/jpeg"):
    result = generate_upload_url(filename, user_id, content_type)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    return result

def parse_iso_datetime(dt_str: str) -> datetime:
    # Standardize 'Z' to '+00:00' to support Python's fromisoformat
    standardized = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(standardized)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

@app.post("/posts/sync")
async def sync_posts(user_id: str):
    """
    Syncs historical posts from ALL connected providers.
    """
    import httpx
    
    # 1. Get Connections (We need to know which services to call)
    # Ideally we'd ask a central registry or check credentials, but for simplicity we'll try all known services
    services = [
        {"name": "facebook", "url": "http://facebook-service:8000/feed"},
        {"name": "instagram", "url": "http://instagram-service:8000/feed"},
        # Add others as implemented:
        # {"name": "linkedin", "url": "http://linkedin-service:8000/feed"},
    ]
    
    synced_count = 0
    
    async with httpx.AsyncClient() as client:
        for svc in services:
            try:
                resp = await client.get(svc['url'], params={"user_id": user_id})
                if resp.status_code == 200:
                    posts = resp.json()
                    for p in posts:
                        # 2. Check overlap logic (Upsert or Insert Ignore)
                        # We use external_id to check existence
                        exists_query = Post.select().where(
                            (Post.c.external_id == p['original_id']) & 
                            (Post.c.platform == p['platform']) &
                            (Post.c.user_id == user_id)
                        )
                        existing = await database.fetch_one(exists_query)
                        
                        if not existing:
                            # Insert
                            query = Post.insert().values(
                                id=uuid.uuid4(),
                                content=p['content'],
                                status=PostStatus.SYNCED.value, # Differentiate from our created posts
                                user_id=user_id,
                                created_at=parse_iso_datetime(p['created_at']) if p.get('created_at') else datetime.utcnow(),
                                external_id=p['original_id'],
                                platform=p['platform']
                            )
                            await database.execute(query)
                            synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync from {svc['name']}: {e}")
                
    return {"status": "success", "synced_count": synced_count}


@app.get("/posts/{post_id}/metrics")
async def get_post_metrics(post_id: uuid.UUID, user_id: str):
    """
    Fetches engagement metrics for a post across all platforms.
    """
    import httpx
    # 1. Fetch the post targets
    query = "SELECT platform, external_id, status FROM post_targets WHERE post_id = :post_id"
    targets = await database.fetch_all(query=query, values={"post_id": post_id})
    
    # Also fetch the post itself to see if it has historical sync attributes
    post_query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(post_query)
    
    metrics_by_platform = {}
    total_metrics = {
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "views": 0
    }
    async def fetch_one(client: httpx.AsyncClient, platform: str, ext_id: str):
        svc_url = f"http://{platform}-service:8000/posts/{ext_id}/metrics"
        try:
            resp = await client.get(svc_url, params={"user_id": user_id}, timeout=5.0)
            if resp.status_code == 200:
                return platform, resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch metrics from {platform}-service for post {ext_id}: {e}")
        return platform, None

    async with httpx.AsyncClient() as client:
        coros = []
        for target in targets:
            platform = target["platform"]
            ext_id = target["external_id"]
            if ext_id:
                coros.append(fetch_one(client, platform, ext_id))
                
        if post and post["status"] == PostStatus.SYNCED.value and post["external_id"] and post["platform"]:
            coros.append(fetch_one(client, post["platform"], post["external_id"]))
            
        if coros:
            results = await asyncio.gather(*coros)
            for platform, p_metrics in results:
                if p_metrics and platform not in metrics_by_platform:
                    metrics_by_platform[platform] = p_metrics
                    for k in total_metrics:
                        total_metrics[k] += p_metrics.get(k, 0)
                        
    return {
        "platforms": metrics_by_platform,
        "total": total_metrics
    }
