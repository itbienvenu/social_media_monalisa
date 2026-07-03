from fastapi import FastAPI, UploadFile, File, HTTPException
from libs.common.serializers import PostCreate, PostResponse, PostStatus, Platform, PostUpdate
from services.post_orchestrator.db import database, Post, PostTarget, PostLog, Notification, AnalyticsSnapshot, metadata, shared_metadata
import sqlalchemy
import asyncio
from services.post_orchestrator.media import generate_upload_url, delete_media_files, get_presigned_download_url
from services.post_orchestrator.events import publish_post_event, mq
import uuid
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import json
import logging
from libs.common.db import connect_db_with_retry
from libs.common.logger import log_post_stage
from arq import create_pool
from arq.connections import RedisSettings
import os

import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("post-orchestrator")

def sanitize_error_message(message: str) -> str:
    if not message:
        return message
    message = re.sub(r'access_token=[^&\s\'"]+', 'access_token=***', message)
    message = re.sub(r'client_secret=[^&\s\'"]+', 'client_secret=***', message)
    message = re.sub(r'code=[^&\s\'"]+', 'code=***', message)
    message = re.sub(r'/uploads(/uploads)+', '/uploads', message)
    return message

def make_user_friendly_error(message: str) -> str:
    message = sanitize_error_message(message)
    def clean_url_match(match):
        url = match.group(0)
        base_url = url.split('?')[0]
        return base_url + "..." if '?' in url else base_url
    message = re.sub(r'https?://[^\s\'"]+', clean_url_match, message)
    return message

async def update_post_overall_status(post_uuid: uuid.UUID, cdn_urls: list = None):
    # Fetch post to see if it is scheduled
    post_query = Post.select().where(Post.c.id == post_uuid)
    post = await database.fetch_one(post_query)
    if not post:
        return
        
    # Fetch all targets
    all_targets_query = PostTarget.select().where(PostTarget.c.post_id == post_uuid)
    targets = await database.fetch_all(all_targets_query)
    statuses = [t["status"] for t in targets]
    
    if not statuses:
        return
        
    is_scheduled_flow = post["scheduled_at"] is not None
        
    if all(s == "published" for s in statuses):
        overall_status = PostStatus.PUBLISHED.value
        scheduler_status = "published" if is_scheduled_flow else post["scheduler_status"]
    elif all(s == "failed" for s in statuses):
        overall_status = PostStatus.FAILED.value
        scheduler_status = "failed" if is_scheduled_flow else post["scheduler_status"]
    elif any(s in ("pending", "processing") for s in statuses):
        overall_status = PostStatus.PROCESSING.value
        scheduler_status = post["scheduler_status"]
    else:
        # Mix of published and failed, and no pending/processing
        overall_status = PostStatus.PARTIAL.value
        scheduler_status = post["scheduler_status"]
        
    update_vals = {
        "status": overall_status,
        "updated_at": datetime.utcnow()
    }
    if is_scheduled_flow:
        update_vals["scheduler_status"] = scheduler_status
        
    if cdn_urls:
        update_vals["media_key"] = cdn_urls[0]
        update_vals["media_keys"] = json.dumps(cdn_urls)
        
    query = Post.update().where(Post.c.id == post_uuid).values(**update_vals)
    await database.execute(query)
    logger.info(f"Updated main post {post_uuid} overall status to {overall_status}")
    
    # If all targets finished, and there were failures, trigger scheduling retry if applicable
    if is_scheduled_flow and not any(s in ("pending", "processing") for s in statuses):
        has_failed_targets = any(s == "failed" for s in statuses)
        if has_failed_targets:
            new_retry_count = (post["retry_count"] or 0) + 1
            if new_retry_count < 3:
                # Reschedule retry in 5 minutes (300 seconds)
                next_attempt = datetime.utcnow() + timedelta(minutes=5)
                await database.execute(
                    Post.update().where(Post.c.id == post_uuid).values(
                        scheduler_status="scheduled",
                        retry_count=new_retry_count,
                        scheduled_at=next_attempt,
                        status=PostStatus.PENDING.value
                    )
                )
                
                # Reset only the failed targets back to pending so they will be retried
                await database.execute(
                    PostTarget.update().where(
                        (PostTarget.c.post_id == post_uuid) & 
                        (PostTarget.c.status == "failed")
                    ).values(status="pending")
                )
                
                await log_post_stage(
                    database, post_uuid, "orchestrator", "retry_scheduled", "WARNING",
                    f"Scheduling retry {new_retry_count}/3 at {next_attempt} due to platform failure"
                )
                await create_notification(
                    user_id=post["user_id"],
                    title="Scheduled post retry",
                    message=f"Scheduled post failed to publish on some platforms. Retrying failed targets in 5 minutes. (Attempt {new_retry_count}/3)",
                    notification_type="warning"
                )
            else:
                # Permanent failure
                await database.execute(
                    Post.update().where(Post.c.id == post_uuid).values(
                        scheduler_status="failed",
                        status=PostStatus.FAILED.value
                    )
                )
                await create_notification(
                    user_id=post["user_id"],
                    title="Scheduled post failed permanently",
                    message=f"Your scheduled post failed permanently after {new_retry_count} attempts.",
                    notification_type="error"
                )

async def create_notification(user_id: str, title: str, message: str, notification_type: str):
    try:
        query = Notification.insert().values(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            read=False,
            created_at=datetime.utcnow()
        )
        await database.execute(query)
        logger.info(f"Created {notification_type} notification for user {user_id}: {title}")
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")

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
        user_id = None
        if existing_post:
            user_id = existing_post["user_id"]
            if existing_post["media_keys"]:
                try:
                    original_keys = json.loads(existing_post["media_keys"])
                except Exception:
                    original_keys = [existing_post["media_keys"]]
        
        # Update main post status dynamically
        await update_post_overall_status(post_uuid, cdn_urls)
        
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
            
        # 4. Send success notification
        if user_id:
            title = f"Posted to {platform.capitalize()}"
            message = f"Your post was successfully published to {platform.capitalize()}."
            await create_notification(user_id, title, message, "success")
            
    except Exception as e:
        logger.error(f"Failed to update post success in DB: {e}")

async def handle_post_failed(data: dict, platform: str):
    post_id = data.get("post_id")
    raw_reason = data.get("reason", "unknown error")
    sanitized_reason = sanitize_error_message(raw_reason)
    user_friendly_reason = make_user_friendly_error(raw_reason)

    logger.info(f"Received failed event for post {post_id} on platform {platform} due to: {sanitized_reason}")
    await log_post_stage(
        database, post_id, "orchestrator", "platform_failed", "ERROR",
        f"Platform '{platform}' posting failed. Reason: {sanitized_reason}"
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

        # 2. Get user_id for notifications
        post_query = Post.select().where(Post.c.id == post_uuid)
        existing_post = await database.fetch_one(post_query)
        user_id = existing_post["user_id"] if existing_post else None

        # 3. Update main post status dynamically
        await update_post_overall_status(post_uuid)
        
        # 4. Send failure notification
        if user_id:
            title = f"Failed to post to {platform.capitalize()}"
            message = f"Failed to publish to {platform.capitalize()}: {user_friendly_reason}"
            await create_notification(user_id, title, message, "error")
            
    except Exception as e:
        logger.error(f"Failed to update post failure in DB: {e}")

def run_multi_account_migration(conn, inspector):
    from libs.common.security import encrypt_token
    import uuid
    
    tables = inspector.get_table_names()
    logger.info(f"Database inspector tables: {tables}")
    
    # 1. Facebook Credentials & Targets
    if "facebook_credentials" in tables:
        try:
            fb_creds = conn.execute(sqlalchemy.text("SELECT id, user_id, access_token FROM facebook_credentials")).fetchall()
            for cred in fb_creds:
                user_id = cred[1]
                access_token = cred[2]
                
                # Check if already migrated
                existing = conn.execute(sqlalchemy.text(
                    "SELECT id FROM social_accounts WHERE user_id = :u AND platform = 'facebook'"
                ), {"u": user_id}).fetchone()
                
                if not existing:
                    account_id = uuid.uuid4()
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_accounts (id, user_id, platform, platform_user_id, account_name) "
                        "VALUES (:id, :u, 'facebook', :p_uid, :name)"
                    ), {
                        "id": account_id,
                        "u": user_id,
                        "p_uid": f"fb_user_{user_id}",
                        "name": "Facebook Account"
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO oauth_tokens (id, account_id, access_token) "
                        "VALUES (:id, :a_id, :tok)"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "tok": encrypt_token(access_token)
                    })
                    logger.info(f"Migrated Facebook Account for user {user_id}")
                    
                    if "facebook_targets" in tables:
                        fb_targets = conn.execute(sqlalchemy.text(
                            "SELECT target_id, target_name, target_type, access_token FROM facebook_targets WHERE user_id = :u"
                        ), {"u": user_id}).fetchall()
                        for target in fb_targets:
                            t_id = target[0]
                            t_name = target[1]
                            t_type = target[2]
                            t_tok = target[3]
                            conn.execute(sqlalchemy.text(
                                "INSERT INTO social_targets (id, account_id, target_id, target_name, target_type, access_token, platform) "
                                "VALUES (:id, :a_id, :t_id, :t_name, :t_type, :t_tok, 'facebook')"
                            ), {
                                "id": uuid.uuid4(),
                                "a_id": account_id,
                                "t_id": t_id,
                                "t_name": t_name,
                                "t_type": t_type,
                                "t_tok": encrypt_token(t_tok) if t_tok else None
                            })
                            logger.info(f"Migrated Facebook Page Target {t_name} for user {user_id}")
        except Exception as e:
            logger.error(f"Error migrating Facebook credentials: {e}")

    # 2. Instagram Targets
    if "instagram_targets" in tables:
        try:
            ig_targets = conn.execute(sqlalchemy.text("SELECT user_id, target_id, target_name, access_token FROM instagram_targets")).fetchall()
            for ig in ig_targets:
                user_id = ig[0]
                target_id = ig[1]
                target_name = ig[2]
                access_token = ig[3]
                
                existing = conn.execute(sqlalchemy.text(
                    "SELECT id FROM social_accounts WHERE user_id = :u AND platform = 'instagram' AND platform_user_id = :p_uid"
                ), {"u": user_id, "p_uid": target_id}).fetchone()
                
                if not existing:
                    account_id = uuid.uuid4()
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_accounts (id, user_id, platform, platform_user_id, account_name) "
                        "VALUES (:id, :u, 'instagram', :p_uid, :name)"
                    ), {
                        "id": account_id,
                        "u": user_id,
                        "p_uid": target_id,
                        "name": target_name
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO oauth_tokens (id, account_id, access_token) "
                        "VALUES (:id, :a_id, :tok)"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "tok": encrypt_token(access_token)
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_targets (id, account_id, target_id, target_name, target_type, access_token, platform) "
                        "VALUES (:id, :a_id, :t_id, :t_name, 'instagram_account', :t_tok, 'instagram')"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "t_id": target_id,
                        "t_name": target_name,
                        "t_tok": encrypt_token(access_token)
                    })
                    logger.info(f"Migrated Instagram Target {target_name} for user {user_id}")
        except Exception as e:
            logger.error(f"Error migrating Instagram targets: {e}")

    # 3. LinkedIn Credentials
    if "linkedin_credentials" in tables:
        try:
            li_creds = conn.execute(sqlalchemy.text("SELECT user_id, linkedin_urn, access_token, refresh_token, expires_at, refresh_expires_at, scope FROM linkedin_credentials")).fetchall()
            for cred in li_creds:
                user_id = cred[0]
                urn = cred[1]
                access_token = cred[2]
                refresh_token = cred[3]
                expires_at = cred[4]
                refresh_expires_at = cred[5]
                scope = cred[6]
                
                existing = conn.execute(sqlalchemy.text(
                    "SELECT id FROM social_accounts WHERE user_id = :u AND platform = 'linkedin' AND platform_user_id = :p_uid"
                ), {"u": user_id, "p_uid": urn}).fetchone()
                
                if not existing:
                    account_id = uuid.uuid4()
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_accounts (id, user_id, platform, platform_user_id, account_name) "
                        "VALUES (:id, :u, 'linkedin', :p_uid, 'LinkedIn Account')"
                    ), {
                        "id": account_id,
                        "u": user_id,
                        "p_uid": urn
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO oauth_tokens (id, account_id, access_token, refresh_token, expires_at, refresh_expires_at, scopes) "
                        "VALUES (:id, :a_id, :tok, :r_tok, :exp, :r_exp, :sc)"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "tok": encrypt_token(access_token),
                        "r_tok": encrypt_token(refresh_token) if refresh_token else None,
                        "exp": expires_at,
                        "r_exp": refresh_expires_at,
                        "sc": scope
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_targets (id, account_id, target_id, target_name, target_type, platform) "
                        "VALUES (:id, :a_id, :t_id, 'LinkedIn Profile', 'personal', 'linkedin')"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "t_id": urn
                    })
                    logger.info(f"Migrated LinkedIn Account for user {user_id}")
        except Exception as e:
            logger.error(f"Error migrating LinkedIn credentials: {e}")

    # 4. TikTok Credentials
    if "tiktok_credentials" in tables:
        try:
            tk_creds = conn.execute(sqlalchemy.text("SELECT user_id, open_id, access_token, refresh_token, expires_at, refresh_expires_at FROM tiktok_credentials")).fetchall()
            for cred in tk_creds:
                user_id = cred[0]
                open_id = cred[1]
                access_token = cred[2]
                refresh_token = cred[3]
                expires_at = cred[4]
                refresh_expires_at = cred[5]
                
                existing = conn.execute(sqlalchemy.text(
                    "SELECT id FROM social_accounts WHERE user_id = :u AND platform = 'tiktok' AND platform_user_id = :p_uid"
                ), {"u": user_id, "p_uid": open_id}).fetchone()
                
                if not existing:
                    account_id = uuid.uuid4()
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_accounts (id, user_id, platform, platform_user_id, account_name) "
                        "VALUES (:id, :u, 'tiktok', :p_uid, 'TikTok Account')"
                    ), {
                        "id": account_id,
                        "u": user_id,
                        "p_uid": open_id
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO oauth_tokens (id, account_id, access_token, refresh_token, expires_at, refresh_expires_at) "
                        "VALUES (:id, :a_id, :tok, :r_tok, :exp, :r_exp)"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "tok": encrypt_token(access_token),
                        "r_tok": encrypt_token(refresh_token) if refresh_token else None,
                        "exp": expires_at,
                        "r_exp": refresh_expires_at
                    })
                    
                    conn.execute(sqlalchemy.text(
                        "INSERT INTO social_targets (id, account_id, target_id, target_name, target_type, platform) "
                        "VALUES (:id, :a_id, :t_id, 'TikTok Profile', 'personal', 'tiktok')"
                    ), {
                        "id": uuid.uuid4(),
                        "a_id": account_id,
                        "t_id": open_id
                    })
                    logger.info(f"Migrated TikTok Account for user {user_id}")
        except Exception as e:
            logger.error(f"Error migrating TikTok credentials: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db_with_retry(database)
    
    # Initialize ARQ pool for background tasks
    redis_pool = await create_pool(RedisSettings(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        database=int(os.getenv('REDIS_DB', 0)),
    ))
    app.state.arq_pool = redis_pool
    
    # Create tables (for simplicity in this monorepo setup)
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
        shared_metadata.create_all(engine)
    except Exception as e:
        logger.warning(f"Table creation skipped or already completed: {e}")
    
    # Run dynamic schema migrations for pre-existing tables
    with engine.begin() as conn:
        try:
            inspector = sqlalchemy.inspect(engine)
            run_multi_account_migration(conn, inspector)
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
                if "audio_key" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN audio_key VARCHAR"))
                    logger.info("Migrated schema: Added column audio_key to posts table")
                if "music_volume" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN music_volume DOUBLE PRECISION DEFAULT 0.2"))
                    logger.info("Migrated schema: Added column music_volume to posts table")
                if "video_volume" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN video_volume DOUBLE PRECISION DEFAULT 1.0"))
                    logger.info("Migrated schema: Added column video_volume to posts table")
                if "slideshow_duration" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN slideshow_duration INTEGER DEFAULT 10"))
                    logger.info("Migrated schema: Added column slideshow_duration to posts table")
                if "job_id" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN job_id VARCHAR"))
                    logger.info("Migrated schema: Added column job_id to posts table")
                if "scheduled_at" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN scheduled_at TIMESTAMP"))
                    logger.info("Migrated schema: Added column scheduled_at to posts table")
                if "timezone" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN timezone VARCHAR"))
                    logger.info("Migrated schema: Added column timezone to posts table")
                if "scheduler_status" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN scheduler_status VARCHAR"))
                    logger.info("Migrated schema: Added column scheduler_status to posts table")
                if "retry_count" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN retry_count INTEGER DEFAULT 0"))
                    logger.info("Migrated schema: Added column retry_count to posts table")
                if "last_attempt_at" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN last_attempt_at TIMESTAMP"))
                    logger.info("Migrated schema: Added column last_attempt_at to posts table")
                if "facebook_page_id" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE posts ADD COLUMN facebook_page_id VARCHAR"))
                    logger.info("Migrated schema: Added column facebook_page_id to posts table")
                
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

        try:
            inspector = sqlalchemy.inspect(engine)
            if "post_targets" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("post_targets")]
                if "target_id" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE post_targets ADD COLUMN target_id VARCHAR"))
                    logger.info("Migrated schema: Added column target_id to post_targets table")
        except Exception as me:
            logger.error(f"Failed to check/migrate post_targets table schema: {me}")

        try:
            inspector = sqlalchemy.inspect(engine)
            if "social_accounts" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("social_accounts")]
                if "username" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE social_accounts ADD COLUMN username VARCHAR"))
                    logger.info("Migrated schema: Added column username to social_accounts table")
                if "display_name" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE social_accounts ADD COLUMN display_name VARCHAR"))
                    logger.info("Migrated schema: Added column display_name to social_accounts table")
                if "profile_picture" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE social_accounts ADD COLUMN profile_picture VARCHAR"))
                    logger.info("Migrated schema: Added column profile_picture to social_accounts table")
        except Exception as me:
            logger.error(f"Failed to check/migrate social_accounts table schema: {me}")

        try:
            inspector = sqlalchemy.inspect(engine)
            if "social_targets" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("social_targets")]
                if "profile_picture" not in columns:
                    conn.execute(sqlalchemy.text("ALTER TABLE social_targets ADD COLUMN profile_picture VARCHAR"))
                    logger.info("Migrated schema: Added column profile_picture to social_targets table")
        except Exception as me:
            logger.error(f"Failed to check/migrate social_targets table schema: {me}")
    
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
    try:
        await app.state.arq_pool.close()
    except Exception:
        pass
    await database.disconnect()

app = FastAPI(title="Post Orchestrator", lifespan=lifespan)

@app.post("/posts", response_model=PostResponse)
async def create_post(post_data: PostCreate, user_id: str):
    import json
    import zoneinfo
    from datetime import timezone as dt_timezone
    from services.post_orchestrator.media import process_and_mix_media
    
    # Resolve Targets
    targets_to_create = []
    platforms_to_post = []
    if post_data.target_ids:
        from libs.common.db_models import SocialTarget, SocialAccount
        import sqlalchemy
        target_rows_query = sqlalchemy.select(
            SocialTarget.c.target_id,
            SocialTarget.c.platform
        ).select_from(
            SocialTarget.join(SocialAccount, SocialTarget.c.account_id == SocialAccount.c.id)
        ).where(
            (SocialAccount.c.user_id == user_id) &
            (SocialTarget.c.target_id.in_(post_data.target_ids))
        )
        rows = await database.fetch_all(target_rows_query)
        if not rows:
            raise HTTPException(status_code=400, detail="No valid social targets found matching the target_ids for this user.")
        
        platforms_set = set()
        for row in rows:
            targets_to_create.append({
                "platform": row["platform"],
                "target_id": row["target_id"]
            })
            platforms_set.add(row["platform"])
        platforms_to_post = list(platforms_set)
    else:
        if not post_data.platforms:
            raise HTTPException(status_code=400, detail="Either platforms or target_ids must be specified.")
        for platform in post_data.platforms:
            platform_str = platform.value if hasattr(platform, "value") else str(platform)
            targets_to_create.append({
                "platform": platform_str,
                "target_id": None
            })
            platforms_to_post.append(platform_str)

    # Validate scheduled_at if provided
    sched_utc = None
    if post_data.scheduled_at:
        try:
            tz = zoneinfo.ZoneInfo(post_data.timezone or "UTC")
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {post_data.timezone}")
        
        sched_dt = post_data.scheduled_at
        if sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=tz)
        
        now_utc = datetime.now(dt_timezone.utc)
        sched_utc = sched_dt.astimezone(dt_timezone.utc)
        if sched_utc <= now_utc:
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    media_key = post_data.media_key
    media_keys = post_data.media_keys
    if not media_key and media_keys:
        media_key = media_keys[0]
    if not media_keys and media_key:
        media_keys = [media_key]
        
    # Check if FFmpeg processing is needed
    needs_processing = False
    if media_keys:
        from services.post_orchestrator.media import is_image_file, is_video_file
        is_all_images = all(is_image_file(k) for k in media_keys)
        is_single_video = len(media_keys) == 1 and is_video_file(media_keys[0])
        needs_slideshow = post_data.is_reel and is_all_images and len(media_keys) > 0
        needs_audio_mix = post_data.audio_key and (needs_slideshow or is_single_video)
        needs_processing = needs_slideshow or needs_audio_mix
    
    job_id = str(uuid.uuid4())
    
    if needs_processing:
        # Enqueue background task for FFmpeg processing
        logger.info(f"Enqueueing background media processing job {job_id}")
        await app.state.arq_pool.enqueue_job(
            'process_media_task',
            job_id=job_id,
            user_id=user_id,
            media_keys=media_keys or [],
            audio_key=post_data.audio_key,
            is_reel=post_data.is_reel,
            music_volume=post_data.music_volume or 0.2,
            video_volume=post_data.video_volume or 1.0,
            slideshow_duration=post_data.slideshow_duration or 10,
            facebook_page_id=post_data.facebook_page_id
        )
        
        # Create post with "processing" status and job_id
        query = Post.insert().values(
            id=uuid.uuid4(),
            content=post_data.content,
            media_key=media_key,
            media_keys=json.dumps(media_keys) if media_keys else None,
            is_reel=post_data.is_reel,
            status=PostStatus.PROCESSING.value,
            user_id=user_id,
            audio_key=post_data.audio_key,
            music_volume=post_data.music_volume,
            video_volume=post_data.video_volume,
            slideshow_duration=post_data.slideshow_duration,
            job_id=job_id,  # Store job_id for tracking
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            scheduled_at=sched_utc.replace(tzinfo=None) if sched_utc else None,
            timezone=post_data.timezone or "UTC" if sched_utc else None,
            scheduler_status="scheduled" if sched_utc else None,
            retry_count=0,
            facebook_page_id=post_data.facebook_page_id
        ).returning(Post)
        
        post = await database.fetch_one(query)
        
        await log_post_stage(
            database, post['id'], "orchestrator", "post_created", "INFO",
            f"Post created with background processing job {job_id}. Targets: {platforms_to_post}"
        )
        
        # Store Metadata (Targets)
        for target in targets_to_create:
            target_query = PostTarget.insert().values(
                id=uuid.uuid4(),
                post_id=post['id'],
                platform=target["platform"],
                status="pending",
                target_id=target["target_id"]
            )
            await database.execute(target_query)
            
        # Return post with processing status (media will be updated when job completes)
        return PostResponse(
            id=post['id'],
            content=post['content'],
            media_key=get_presigned_download_url(post['media_key']),
            media_keys=[get_presigned_download_url(k) for k in json.loads(post['media_keys'])] if post['media_keys'] else None,
            platforms=[Platform(p) for p in platforms_to_post if p in [pl.value for pl in Platform]],
            is_reel=post['is_reel'],
            status=PostStatus(post['status']),
            created_at=post['created_at'],
            updated_at=post['updated_at'],
            scheduled_at=post['scheduled_at'],
            timezone=post['timezone'],
            scheduler_status=post['scheduler_status'],
            retry_count=post['retry_count'],
            last_attempt_at=post['last_attempt_at']
        )
    else:
        # No processing needed, proceed as before
        compiled_result = await process_and_mix_media(
            user_id=user_id,
            media_keys=media_keys or [],
            audio_key=post_data.audio_key,
            is_reel=post_data.is_reel,
            music_volume=post_data.music_volume or 0.2,
            video_volume=post_data.video_volume or 1.0,
            slideshow_duration=post_data.slideshow_duration or 10
        )
        
        if compiled_result:
            media_key = compiled_result["media_key"]
            media_keys = compiled_result["media_keys"]
            post_data.media_key = media_key
            post_data.media_keys = media_keys

    # 1. Store in DB
    query = Post.insert().values(
        id=uuid.uuid4(),
        content=post_data.content,
        media_key=media_key,
        media_keys=json.dumps(media_keys) if media_keys else None,
        is_reel=post_data.is_reel,
        status=PostStatus.PENDING.value,
        user_id=user_id,
        audio_key=post_data.audio_key,
        music_volume=post_data.music_volume,
        video_volume=post_data.video_volume,
        slideshow_duration=post_data.slideshow_duration,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        scheduled_at=sched_utc.replace(tzinfo=None) if sched_utc else None,
        timezone=post_data.timezone or "UTC" if sched_utc else None,
        scheduler_status="scheduled" if sched_utc else None,
        retry_count=0,
        facebook_page_id=post_data.facebook_page_id
    ).returning(Post)
    
    post = await database.fetch_one(query)
    
    await log_post_stage(
        database, post['id'], "orchestrator", "post_created", "INFO",
        f"Post created in database. Targets: {platforms_to_post}"
    )
    
    # 2. Store Metadata (Targets)
    for target in targets_to_create:
        target_query = PostTarget.insert().values(
            id=uuid.uuid4(),
            post_id=post['id'],
            platform=target["platform"],
            status="pending",
            target_id=target["target_id"]
        )
        await database.execute(target_query)
        
    # 3. Publish Events if NOT scheduled
    if not post_data.scheduled_at:
        failed_platforms = []
        for target in targets_to_create:
            platform_str = target["platform"]
            try:
                try:
                    platform_enum = Platform(platform_str)
                except ValueError:
                    platform_enum = platform_str
                
                await publish_post_event(
                    post_id=post['id'], 
                    platform=platform_enum, 
                    content=post_data.content, 
                    media_key=post_data.media_key, 
                    user_id=user_id,
                    media_keys=post_data.media_keys,
                    is_reel=post_data.is_reel,
                    facebook_page_id=post_data.facebook_page_id,
                    target_id=target["target_id"]
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
        platforms=[Platform(p) for p in platforms_to_post if p in [pl.value for pl in Platform]],
        is_reel=post['is_reel'],
        status=PostStatus(post['status']),
        created_at=post['created_at'],
        updated_at=post['updated_at'],
        scheduled_at=post['scheduled_at'],
        timezone=post['timezone'],
        scheduler_status=post['scheduler_status'],
        retry_count=post['retry_count'],
        last_attempt_at=post['last_attempt_at']
    )


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
    import zoneinfo
    from datetime import timezone as dt_timezone
    
    # 1. Fetch post
    post_query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(post_query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    user_id = post["user_id"]
    is_scheduled_state = post["scheduler_status"] in ("scheduled", "cancelled", "failed")
    
    # 2. Fetch targets
    targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
    targets = await database.fetch_all(targets_query)

    if not is_scheduled_state:
        # Published post path
        if update_data.scheduled_at is not None or update_data.timezone is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot reschedule an already published post"
            )
            
        # Update the post message/caption on each platform
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

        # Update local database content
        update_vals = {"updated_at": datetime.utcnow()}
        if update_data.content is not None:
            update_vals["content"] = update_data.content
            
        update_query = (
            Post.update()
            .where(Post.c.id == post_id)
            .values(**update_vals)
        )
        await database.execute(update_query)
        
    else:
        # Scheduled/cancelled/failed post path
        update_vals = {"updated_at": datetime.utcnow()}
        
        if update_data.content is not None:
            update_vals["content"] = update_data.content
            
        tz_name = update_data.timezone or post["timezone"] or "UTC"
        if update_data.timezone is not None:
            try:
                zoneinfo.ZoneInfo(update_data.timezone)
                update_vals["timezone"] = update_data.timezone
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {update_data.timezone}")
                
        if update_data.scheduled_at is not None:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz_name}")
                
            sched_dt = update_data.scheduled_at
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=tz)
                
            now_utc = datetime.now(dt_timezone.utc)
            sched_utc = sched_dt.astimezone(dt_timezone.utc)
            if sched_utc <= now_utc:
                raise HTTPException(status_code=400, detail="Scheduled time must be in the future")
                
            update_vals["scheduled_at"] = sched_utc.replace(tzinfo=None)
            update_vals["scheduler_status"] = "scheduled"
            update_vals["retry_count"] = 0
            update_vals["last_attempt_at"] = None
            update_vals["status"] = PostStatus.PENDING.value
            
            # Reset target statuses back to pending
            await database.execute(
                PostTarget.update()
                .where(PostTarget.c.post_id == post_id)
                .values(status="pending")
            )
            
            await log_post_stage(
                database, post_id, "orchestrator", "scheduled_rescheduled", "INFO",
                f"Scheduled post was updated/rescheduled to {sched_utc.replace(tzinfo=None)} UTC."
            )

        update_query = (
            Post.update()
            .where(Post.c.id == post_id)
            .values(**update_vals)
        )
        await database.execute(update_query)

    # Fetch updated post to return
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
        updated_at=updated_post['updated_at'],
        scheduled_at=updated_post['scheduled_at'],
        timezone=updated_post['timezone'],
        scheduler_status=updated_post['scheduler_status'],
        retry_count=updated_post['retry_count'],
        last_attempt_at=updated_post['last_attempt_at']
    )

@app.post("/posts/{post_id}/cancel", response_model=PostResponse)
async def cancel_scheduled_post(post_id: uuid.UUID):
    # 1. Fetch post
    post_query = Post.select().where(Post.c.id == post_id)
    post = await database.fetch_one(post_query)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # Check if the post is scheduled
    if post["scheduler_status"] != "scheduled":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel post in state: {post['scheduler_status'] or 'not scheduled'}"
        )
        
    # Update status to cancelled
    update_query = (
        Post.update()
        .where(Post.c.id == post_id)
        .values(
            scheduler_status="cancelled", 
            status=PostStatus.FAILED.value,
            updated_at=datetime.utcnow()
        )
    )
    await database.execute(update_query)
    
    # Update targets to failed/cancelled
    await database.execute(
        PostTarget.update()
        .where(PostTarget.c.post_id == post_id)
        .values(status="cancelled")
    )
    
    await log_post_stage(
        database, post_id, "orchestrator", "scheduled_cancelled", "INFO",
        "Scheduled post was cancelled by user."
    )
    
    # Fetch updated post
    updated_post = await database.fetch_one(post_query)
    targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
    targets = await database.fetch_all(targets_query)
    platforms_list = [Platform(t["platform"]) for t in targets if t["platform"] in Platform.__members__.values()]
    if not platforms_list:
        platforms_list = [Platform.FACEBOOK]
        
    return PostResponse(
        id=updated_post['id'],
        content=updated_post['content'],
        media_key=get_presigned_download_url(updated_post['media_key']),
        media_keys=[get_presigned_download_url(k) for k in json.loads(updated_post['media_keys'])] if updated_post['media_keys'] else None,
        platforms=platforms_list,
        is_reel=updated_post['is_reel'],
        status=PostStatus(updated_post['status']),
        created_at=updated_post['created_at'],
        updated_at=updated_post['updated_at'],
        scheduled_at=updated_post['scheduled_at'],
        timezone=updated_post['timezone'],
        scheduler_status=updated_post['scheduler_status'],
        retry_count=updated_post['retry_count'],
        last_attempt_at=updated_post['last_attempt_at']
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
        updated_at=post['updated_at'],
        scheduled_at=post['scheduled_at'],
        timezone=post['timezone'],
        scheduler_status=post['scheduler_status'],
        retry_count=post['retry_count'],
        last_attempt_at=post['last_attempt_at']
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
            updated_at=p['updated_at'] or p['created_at'] or datetime.utcnow(),
            scheduled_at=p['scheduled_at'],
            timezone=p['timezone'],
            scheduler_status=p['scheduler_status'],
            retry_count=p['retry_count'],
            last_attempt_at=p['last_attempt_at']
        ))
    return results

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a background media processing job."""
    import redis.asyncio as redis
    
    redis_client = await redis.from_url(
        f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/{os.getenv('REDIS_DB', 0)}"
    )
    
    job_data = await redis_client.get(f"job:{job_id}")
    await redis_client.close()
    
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    
    return json.loads(job_data)

@app.post("/media/upload-url")
async def get_upload_url(filename: str, user_id: str, content_type: str = "image/jpeg"):
    result = generate_upload_url(filename, user_id, content_type)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    return result

def parse_iso_datetime(dt_str: str) -> datetime:
    # Standardize 'Z' to '+00:00' to support Python's fromisoformat
    standardized = dt_str.replace("Z", "+00:00")
    # Handle offsets like +0000 by adding a colon if needed
    if len(standardized) >= 5 and standardized[-5] in ('+', '-'):
        if ":" not in standardized[-3:]:
            standardized = standardized[:-2] + ":" + standardized[-2:]
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
    services = [
        {"name": "facebook", "url": "http://facebook-service:8000/feed"},
        {"name": "instagram", "url": "http://instagram-service:8000/feed"},
    ]
    
    synced_count = 0
    
    async with httpx.AsyncClient() as client:
        for svc in services:
            platform = svc["name"]
            try:
                resp = await client.get(svc['url'], params={"user_id": user_id})
                if resp.status_code == 200:
                    posts = resp.json()
                    for p in posts:
                        ext_id = p['original_id']
                        # Check existence
                        exists_query = Post.select().where(
                            (Post.c.external_id == ext_id) & 
                            (Post.c.platform == platform) &
                            (Post.c.user_id == user_id)
                        )
                        existing = await database.fetch_one(exists_query)
                        
                        if not existing:
                            new_post_id = uuid.uuid4()
                            post_created_at = parse_iso_datetime(p['created_at']) if p.get('created_at') else datetime.utcnow()
                            
                            # Insert Post
                            query = Post.insert().values(
                                id=new_post_id,
                                content=p['content'],
                                status=PostStatus.SYNCED.value, # Differentiate from our created posts
                                user_id=user_id,
                                created_at=post_created_at,
                                updated_at=post_created_at,
                                external_id=ext_id,
                                platform=platform
                            )
                            await database.execute(query)
                            synced_count += 1
                            
                            # Immediately pull current metrics to backfill snapshots
                            metrics = {"likes": 0, "comments": 0, "shares": 0, "views": 0}
                            metrics_url = f"http://{platform}-service:8000/posts/{ext_id}/metrics"
                            try:
                                m_resp = await client.get(metrics_url, params={"user_id": user_id}, timeout=5.0)
                                if m_resp.status_code == 200:
                                    metrics = m_resp.json()
                            except Exception as me:
                                logger.error(f"Failed to fetch initial metrics for synced post {ext_id} during backfill: {me}")
                            
                            # Backfill snapshots up to 30 days
                            now = datetime.utcnow()
                            delta_days = (now - post_created_at).days
                            start_backfill_days = min(max(0, delta_days), 30)
                            
                            for day_offset in range(start_backfill_days + 1):
                                snapshot_time = now - timedelta(days=start_backfill_days - day_offset)
                                
                                # Estimate daily metric counts using a growth factor
                                fraction = (day_offset + 1) / (start_backfill_days + 1)
                                scale = fraction * fraction
                                
                                likes = int(metrics.get("likes", 0) * scale)
                                comments = int(metrics.get("comments", 0) * scale)
                                shares = int(metrics.get("shares", 0) * scale)
                                views = int(metrics.get("views", 0) * scale)
                                
                                # Insert snapshot
                                snapshot_query = AnalyticsSnapshot.insert().values(
                                    id=uuid.uuid4(),
                                    post_id=new_post_id,
                                    platform=platform,
                                    likes=likes,
                                    comments=comments,
                                    shares=shares,
                                    views=views,
                                    timestamp=snapshot_time
                                )
                                await database.execute(snapshot_query)
                                logger.info(f"Backfilled snapshot for post {new_post_id} on {snapshot_time}")
                                
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


@app.get("/notifications")
async def get_notifications(user_id: str):
    query = Notification.select().where(Notification.c.user_id == user_id).order_by(Notification.c.created_at.desc())
    return await database.fetch_all(query)


@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: uuid.UUID, user_id: str):
    query = Notification.update().where(
        (Notification.c.id == notification_id) & (Notification.c.user_id == user_id)
    ).values(read=True)
    await database.execute(query)
    return {"status": "success"}


@app.post("/notifications/read-all")
async def mark_all_notifications_read(user_id: str):
    query = Notification.update().where(Notification.c.user_id == user_id).values(read=True)
    await database.execute(query)
    return {"status": "success"}


# --- Multi-Account Management Endpoints ---

from pydantic import BaseModel
from typing import List

class UpdatePreferencesPayload(BaseModel):
    preferred_target_ids: List[str]


@app.get("/connections")
async def get_connections(user_id: str):
    from libs.common.db_models import SocialAccount, SocialTarget
    import sqlalchemy

    # Fetch accounts
    accounts_query = SocialAccount.select().where(SocialAccount.c.user_id == user_id)
    accounts = await database.fetch_all(accounts_query)

    # Fetch targets
    targets_query = SocialTarget.select().where(
        SocialTarget.c.account_id.in_([acc["id"] for acc in accounts])
    ) if accounts else None

    targets = await database.fetch_all(targets_query) if targets_query is not None else []

    # Map targets by account_id
    targets_by_account = {}
    for tgt in targets:
        acc_id = tgt["account_id"]
        if acc_id not in targets_by_account:
            targets_by_account[acc_id] = []
        targets_by_account[acc_id].append({
            "id": str(tgt["id"]),
            "target_id": tgt["target_id"],
            "target_name": tgt["target_name"],
            "target_type": tgt["target_type"],
            "platform": tgt["platform"],
            "is_preferred": tgt["is_preferred"],
            "profile_picture": tgt["profile_picture"]
        })

    result = []
    for acc in accounts:
        acc_id = acc["id"]
        result.append({
            "id": acc_id,
            "platform": acc["platform"],
            "username": acc["username"],
            "display_name": acc["display_name"],
            "profile_picture": acc["profile_picture"],
            "created_at": acc["created_at"].isoformat() if acc["created_at"] else None,
            "targets": targets_by_account.get(acc_id, [])
        })

    return result


@app.delete("/connections/{account_id}")
async def disconnect_account(account_id: str, user_id: str):
    import uuid
    from libs.common.db_models import SocialAccount, SocialTarget, OAuthToken, TokenRefreshMetadata
    try:
        acc_uuid = uuid.UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid account_id format")

    # Verify ownership
    check_query = SocialAccount.select().where(
        (SocialAccount.c.id == acc_uuid) & (SocialAccount.c.user_id == user_id)
    )
    acc = await database.fetch_one(check_query)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found or unauthorized")

    # Delete related targets
    await database.execute(SocialTarget.delete().where(SocialTarget.c.account_id == acc_uuid))
    # Delete related refresh metadata
    await database.execute(TokenRefreshMetadata.delete().where(TokenRefreshMetadata.c.account_id == acc_uuid))
    # Delete related oauth token
    await database.execute(OAuthToken.delete().where(OAuthToken.c.account_id == acc_uuid))
    # Delete account
    await database.execute(SocialAccount.delete().where(SocialAccount.c.id == acc_uuid))

    return {"status": "success", "message": "Account disconnected successfully"}


@app.get("/connections/targets")
async def get_all_targets(user_id: str):
    from libs.common.db_models import SocialAccount, SocialTarget
    import sqlalchemy

    query = sqlalchemy.select(
        SocialTarget.c.id,
        SocialTarget.c.target_id,
        SocialTarget.c.target_name,
        SocialTarget.c.target_type,
        SocialTarget.c.platform,
        SocialTarget.c.is_preferred,
        SocialTarget.c.profile_picture,
        SocialAccount.c.display_name.label("account_name"),
        SocialAccount.c.username.label("account_username")
    ).select_from(
        SocialTarget.join(SocialAccount, SocialTarget.c.account_id == SocialAccount.c.id)
    ).where(
        SocialAccount.c.user_id == user_id
    )
    
    targets = await database.fetch_all(query)
    return [
        {
            "id": str(t["id"]),
            "target_id": t["target_id"],
            "target_name": t["target_name"],
            "target_type": t["target_type"],
            "platform": t["platform"],
            "is_preferred": t["is_preferred"],
            "profile_picture": t["profile_picture"],
            "account_name": t["account_name"],
            "account_username": t["account_username"]
        }
        for t in targets
    ]


@app.put("/connections/preferences")
async def update_target_preferences(payload: UpdatePreferencesPayload, user_id: str):
    from libs.common.db_models import SocialAccount, SocialTarget
    import sqlalchemy

    # Fetch all target IDs belonging to the user's connected accounts to ensure security/ownership
    user_targets_query = sqlalchemy.select(SocialTarget.c.target_id).select_from(
        SocialTarget.join(SocialAccount, SocialTarget.c.account_id == SocialAccount.c.id)
    ).where(
        SocialAccount.c.user_id == user_id
    )
    user_targets_rows = await database.fetch_all(user_targets_query)
    allowed_target_ids = {row["target_id"] for row in user_targets_rows}

    # Filter to only allowed IDs
    target_ids_to_prefer = [tid for tid in payload.preferred_target_ids if tid in allowed_target_ids]

    # Set all of user's targets to preferred = False
    deactivate_query = SocialTarget.update().where(
        SocialTarget.c.account_id.in_(
            sqlalchemy.select(SocialAccount.c.id).where(SocialAccount.c.user_id == user_id)
        )
    ).values(is_preferred=False)
    await database.execute(deactivate_query)

    # Set specified targets to preferred = True
    if target_ids_to_prefer:
        activate_query = SocialTarget.update().where(
            SocialTarget.c.target_id.in_(target_ids_to_prefer)
        ).values(is_preferred=True)
        await database.execute(activate_query)

    return {"status": "success", "message": "Preferences updated successfully"}
