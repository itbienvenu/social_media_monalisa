from fastapi import FastAPI, UploadFile, File, HTTPException
from libs.common.serializers import PostCreate, PostResponse, PostStatus, Platform
from services.post_orchestrator.db import database, Post, PostTarget, metadata
import sqlalchemy
from services.post_orchestrator.media import generate_upload_url
from services.post_orchestrator.events import publish_post_event, mq
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("post-orchestrator")

async def handle_post_success(data: dict, platform: str):
    post_id = data.get("post_id")
    platform_post_id = data.get("platform_post_id")
    logger.info(f"Received success event for post {post_id} on platform {platform}")
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

        # 2. Update main post status to published
        query = Post.update().where(Post.c.id == post_uuid).values(
            status=PostStatus.PUBLISHED.value,
            updated_at=datetime.utcnow()
        )
        await database.execute(query)
        logger.info(f"Successfully updated post {post_id} target ({platform}) to PUBLISHED in DB")
    except Exception as e:
        logger.error(f"Failed to update post success in DB: {e}")

async def handle_post_failed(data: dict, platform: str):
    post_id = data.get("post_id")
    reason = data.get("reason", "unknown error")
    logger.info(f"Received failed event for post {post_id} on platform {platform} due to: {reason}")
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
    # Create tables (for simplicity in this monorepo setup)
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
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
            
    await database.connect()
    
    # Start RabbitMQ subscriptions
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
