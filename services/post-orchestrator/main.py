from fastapi import FastAPI, UploadFile, File, HTTPException
from libs.common.serializers import PostCreate, PostResponse, PostStatus, Platform
from services.post_orchestrator.db import database, Post, PostTarget, metadata
import sqlalchemy
from services.post_orchestrator.media import generate_upload_url
from services.post_orchestrator.events import publish_post_event
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("post-orchestrator")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (for simplicity in this monorepo setup)
    # In prod, use Alembic migrations.
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    yield
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
    # Simplified: We just assume we store them. In a real app we'd batch insert targets.
    # For now just trigger events.
    
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
