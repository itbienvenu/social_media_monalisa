from fastapi import FastAPI, UploadFile, File, HTTPException
from libs.common.serializers import PostCreate, PostResponse, PostStatus, Platform
from services.post_orchestrator.db import database, Post, PostTarget, metadata
import sqlalchemy
from services.post_orchestrator.media import generate_upload_url
from services.post_orchestrator.events import publish_post_event, mq
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("post-orchestrator")

async def handle_post_success(data: dict):
    post_id = data.get("post_id")
    platform_post_id = data.get("platform_post_id")
    logger.info(f"Received success event for post {post_id}")
    try:
        post_uuid = uuid.UUID(post_id)
        # Update main post status to published
        query = Post.update().where(Post.c.id == post_uuid).values(
            status=PostStatus.PUBLISHED.value,
            updated_at=datetime.utcnow()
        )
        await database.execute(query)
        
        # Update target status
        target_query = PostTarget.update().where(
            PostTarget.c.post_id == post_uuid
        ).values(
            status="published",
            external_id=platform_post_id
        )
        await database.execute(target_query)
        logger.info(f"Successfully updated post {post_id} to PUBLISHED in DB")
    except Exception as e:
        logger.error(f"Failed to update post success in DB: {e}")

async def handle_post_failed(data: dict):
    post_id = data.get("post_id")
    reason = data.get("reason", "unknown error")
    logger.info(f"Received failed event for post {post_id} due to: {reason}")
    try:
        post_uuid = uuid.UUID(post_id)
        # Update main post status to failed
        query = Post.update().where(Post.c.id == post_uuid).values(
            status=PostStatus.FAILED.value,
            updated_at=datetime.utcnow()
        )
        await database.execute(query)
        
        # Update target status
        target_query = PostTarget.update().where(
            PostTarget.c.post_id == post_uuid
        ).values(
            status="failed"
        )
        await database.execute(target_query)
        logger.info(f"Successfully updated post {post_id} to FAILED in DB")
    except Exception as e:
        logger.error(f"Failed to update post failure in DB: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (for simplicity in this monorepo setup)
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    
    # Start RabbitMQ subscriptions
    try:
        await mq.connect()
        for platform in ["facebook", "tiktok", "linkedin", "instagram"]:
            await mq.subscribe(f"posts.{platform}.success", handle_post_success)
            await mq.subscribe(f"posts.{platform}.failed", handle_post_failed)
        logger.info("Successfully subscribed to posts success and failure events")
    except Exception as e:
        logger.error(f"Failed to setup RabbitMQ subscriptions in post-orchestrator: {e}")
        
    yield
    try:
        await mq.disconnect()
    except Exception:
        pass
    await database.disconnect()

app = FastAPI(title="Post Orchestrator", lifespan=lifespan)

@app.post("/posts", response_model=PostResponse)
async def create_post(post_data: PostCreate, user_id: str):
    # 1. Store in DB
    query = Post.insert().values(
        id=uuid.uuid4(),
        content=post_data.content,
        media_key=post_data.media_key,
        status=PostStatus.PENDING.value,
        user_id=user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    ).returning(Post)
    
    post = await database.fetch_one(query)
    
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
    for platform in post_data.platforms:
        await publish_post_event(post['id'], platform, post_data.content, post_data.media_key, user_id)
        
    return PostResponse(
        id=post['id'],
        content=post['content'],
        media_key=post['media_key'],
        platforms=post_data.platforms,
        status=PostStatus(post['status']),
        created_at=post['created_at'],
        updated_at=post['updated_at']
    )

@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: uuid.UUID):
    query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # Mocking platforms fetching for read
    return PostResponse(
        id=post['id'],
        content=post['content'],
        media_key=post['media_key'],
        platforms=[Platform.FACEBOOK], # Mocked
        status=PostStatus(post['status']),
        created_at=post['created_at'],
        updated_at=post['updated_at']
    )

@app.get("/posts", response_model=list[PostResponse])
async def list_posts(user_id: str):
    query = Post.select().where(Post.c.user_id == user_id).order_by(Post.c.created_at.desc())
    posts = await database.fetch_all(query)
    
    return [
        PostResponse(
            id=p['id'],
            content=p['content'],
            media_key=p['media_key'],
            platforms=[Platform.FACEBOOK], # Mocked for list view for now
            status=PostStatus(p['status']),
            created_at=p['created_at'],
            updated_at=p['updated_at']
        ) for p in posts
    ]

@app.post("/media/upload-url")
async def get_upload_url(filename: str, content_type: str = "image/jpeg"):
    result = generate_upload_url(filename, content_type)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    return result

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
                            (Post.c.platform == p['platform'])
                        )
                        existing = await database.fetch_one(exists_query)
                        
                        if not existing:
                            # Insert
                            query = Post.insert().values(
                                id=uuid.uuid4(),
                                content=p['content'],
                                status="synced", # Differentiate from our created posts
                                user_id=user_id,
                                created_at=datetime.fromisoformat(p['created_at'].replace("T", " ").split("+")[0]) if p.get('created_at') else datetime.utcnow(),
                                external_id=p['original_id'],
                                platform=p['platform']
                            )
                            await database.execute(query)
                            synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync from {svc['name']}: {e}")
                
    return {"status": "success", "synced_count": synced_count}
