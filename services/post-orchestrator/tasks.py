import os
import asyncio
from arq import cron
from services.post_orchestrator.media import process_and_mix_media
from services.post_orchestrator.db import database, Post, PostTarget, Notification
import uuid
import json
from datetime import datetime
from logging import getLogger
from libs.common.logger import log_post_stage
from services.post_orchestrator.events import publish_post_event
from libs.common.serializers import Platform, PostStatus

logger = getLogger("post-orchestrator.tasks")

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
        logger.error(f"Failed to create notification in background task: {e}")

async def process_media_task(ctx, job_id: str, user_id: str, media_keys: list, audio_key: str = None, 
                            is_reel: bool = False, music_volume: float = 0.2, video_volume: float = 1.0, 
                            slideshow_duration: int = 10, facebook_page_id: str = None):
    """
    Background task to process media (FFmpeg compilation) without blocking the HTTP request.
    """
    post_uuid = None
    try:
        logger.info(f"Starting media processing job {job_id} for user {user_id}")
        
        # Find matching post
        post_query = Post.select().where(Post.c.job_id == job_id)
        post = await database.fetch_one(post_query)
        if not post:
            logger.error(f"No post found for job_id {job_id}")
            await update_job_status(job_id, "failed", 0, "No post found for this job")
            return
            
        post_uuid = post['id']
        
        # Update job status to processing
        await update_job_status(job_id, "processing", 0, "Starting FFmpeg processing")
        await log_post_stage(
            database, post_uuid, "orchestrator", "processing_media", "INFO",
            f"Background media processing started for job_id {job_id}"
        )
        
        # Process media with FFmpeg
        compiled_result = await process_and_mix_media(
            user_id=user_id,
            media_keys=media_keys,
            audio_key=audio_key,
            is_reel=is_reel,
            music_volume=music_volume,
            video_volume=video_volume,
            slideshow_duration=slideshow_duration
        )
        
        # Update Post and targets
        if compiled_result:
            update_vals = {
                "media_key": compiled_result["media_key"],
                "media_keys": json.dumps(compiled_result["media_keys"]),
                "status": PostStatus.PENDING.value,
                "updated_at": datetime.utcnow()
            }
            update_query = Post.update().where(Post.c.id == post_uuid).values(**update_vals)
            await database.execute(update_query)
            
            await update_job_status(job_id, "completed", 100, "Media processing completed successfully", 
                                   result=compiled_result)
            logger.info(f"Job {job_id} completed successfully")
            await log_post_stage(
                database, post_uuid, "orchestrator", "processing_completed", "INFO",
                f"Media processing completed successfully. Compiled media key: {compiled_result['media_key']}"
            )
        else:
            # No processing needed or fallback
            update_vals = {
                "status": PostStatus.PENDING.value,
                "updated_at": datetime.utcnow()
            }
            update_query = Post.update().where(Post.c.id == post_uuid).values(**update_vals)
            await database.execute(update_query)
            
            await update_job_status(job_id, "completed", 100, "No processing needed (already video format)")
            logger.info(f"Job {job_id} completed - no processing needed")
            await log_post_stage(
                database, post_uuid, "orchestrator", "processing_skipped", "INFO",
                "Media processing completed (no compilation/mixing was required)"
            )
        # Check if the post is scheduled. If it is scheduled, we do NOT publish yet!
        if post.get("scheduled_at") is not None and post.get("scheduler_status") == "scheduled":
            logger.info(f"Post {post_uuid} is scheduled for {post['scheduled_at']}. Skipping immediate publication.")
            await log_post_stage(
                database, post_uuid, "orchestrator", "scheduling_saved", "INFO",
                f"Media compilation finished. Post is scheduled for {post['scheduled_at']}."
            )
            return compiled_result
            
        # Publish Events to RabbitMQ for targets
        targets_query = PostTarget.select().where(PostTarget.c.post_id == post_uuid)
        targets = await database.fetch_all(targets_query)
        
        for target in targets:
            platform_str = target["platform"]
            try:
                try:
                    platform_enum = Platform(platform_str)
                except ValueError:
                    platform_enum = platform_str
                
                final_media_key = compiled_result["media_key"] if compiled_result else post["media_key"]
                final_media_keys = compiled_result["media_keys"] if compiled_result else (json.loads(post["media_keys"]) if post["media_keys"] else [])
                
                await publish_post_event(
                    post_id=post_uuid,
                    platform=platform_enum,
                    content=post["content"],
                    media_key=final_media_key,
                    user_id=user_id,
                    media_keys=final_media_keys,
                    is_reel=is_reel,
                    facebook_page_id=facebook_page_id
                )
                
                await log_post_stage(
                    database, post_uuid, "orchestrator", "event_published", "INFO",
                    f"Successfully published post event to posts.{platform_str}"
                )
            except Exception as publish_err:
                logger.error(f"Failed to publish post event to {platform_str} in background worker: {publish_err}")
                await log_post_stage(
                    database, post_uuid, "orchestrator", "publish_failed", "ERROR",
                    f"Failed to publish post event to {platform_str} in background worker: {publish_err}"
                )
                # Update target status to failed
                update_target_query = PostTarget.update().where(
                    (PostTarget.c.post_id == post_uuid) & 
                    (PostTarget.c.platform == platform_str)
                ).values(status="failed")
                await database.execute(update_target_query)
        
        # Trigger an overall status update after publishing (if some failed to publish)
        await update_post_overall_status(post_uuid)
        return compiled_result
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await update_job_status(job_id, "failed", 0, f"Processing failed: {str(e)}")
        
        if post_uuid:
            await log_post_stage(
                database, post_uuid, "orchestrator", "processing_failed", "ERROR",
                f"Media processing failed: {str(e)}"
            )
            # Update post status to failed
            update_query = Post.update().where(Post.c.id == post_uuid).values(
                status=PostStatus.FAILED.value,
                updated_at=datetime.utcnow()
            )
            await database.execute(update_query)
            
            # Update all pending/processing targets to failed
            update_targets_query = PostTarget.update().where(
                (PostTarget.c.post_id == post_uuid) & 
                (PostTarget.c.status.in_(["pending", "processing"]))
            ).values(status="failed")
            await database.execute(update_targets_query)
            
            # Send notification
            await create_notification(
                user_id=user_id,
                title="Media processing failed",
                message=f"Failed to process media for your post: {str(e)}",
                notification_type="error"
            )
        raise

async def update_post_overall_status(post_uuid: uuid.UUID):
    # Fetch all targets
    all_targets_query = PostTarget.select().where(PostTarget.c.post_id == post_uuid)
    targets = await database.fetch_all(all_targets_query)
    statuses = [t["status"] for t in targets]
    
    if not statuses:
        return
        
    if all(s == "published" for s in statuses):
        overall_status = PostStatus.PUBLISHED.value
    elif all(s == "failed" for s in statuses):
        overall_status = PostStatus.FAILED.value
    elif any(s in ("pending", "processing") for s in statuses):
        overall_status = PostStatus.PROCESSING.value
    else:
        overall_status = PostStatus.PARTIAL.value
        
    update_vals = {
        "status": overall_status,
        "updated_at": datetime.utcnow()
    }
    query = Post.update().where(Post.c.id == post_uuid).values(**update_vals)
    await database.execute(query)
    logger.info(f"Updated main post {post_uuid} overall status to {overall_status}")

async def update_job_status(job_id: str, status: str, progress: int, message: str, result: dict = None):
    """
    Update job status in Redis for status polling.
    """
    import redis.asyncio as redis
    
    redis_client = await redis.from_url(
        f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/{os.getenv('REDIS_DB', 0)}"
    )
    
    job_data = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if result:
        job_data["result"] = result
    
    await redis_client.setex(f"job:{job_id}", 3600, json.dumps(job_data))  # Expire after 1 hour
    await redis_client.close()

async def check_scheduled_posts(ctx):
    """
    Cron task to find and publish scheduled posts whose scheduled_at <= now,
    and scheduler_status == 'scheduled'.
    """
    from datetime import datetime
    import datetime as dt_module
    import json
    
    logger.info("Checking for scheduled posts...")
    
    now = datetime.utcnow()
    
    # 1. Atomically claim posts by updating scheduler_status to 'publishing' and returning them.
    # This prevents worker race conditions when multiple worker instances run concurrently.
    claim_query = (
        Post.update()
        .where(
            (Post.c.scheduled_at <= now) &
            (Post.c.scheduler_status == "scheduled") &
            (Post.c.status == PostStatus.PENDING.value)
        )
        .values(
            scheduler_status="publishing",
            last_attempt_at=now
        )
        .returning(
            Post.c.id,
            Post.c.user_id,
            Post.c.content,
            Post.c.media_key,
            Post.c.media_keys,
            Post.c.is_reel,
            Post.c.facebook_page_id,
            Post.c.retry_count
        )
    )
    scheduled_posts = await database.fetch_all(claim_query)
    
    if not scheduled_posts:
        return
        
    logger.info(f"Claimed {len(scheduled_posts)} scheduled posts to publish")
    
    async def process_claimed_post(post):
        post = dict(post)
        post_id = post["id"]
        user_id = post["user_id"]
        
        logger.info(f"Publishing claimed scheduled post {post_id}")
        
        # 2. Fetch targets
        targets_query = PostTarget.select().where(PostTarget.c.post_id == post_id)
        targets = await database.fetch_all(targets_query)
        
        failed_publish = False
        last_error = None
        
        # Get media keys
        try:
            m_keys = json.loads(post["media_keys"]) if post["media_keys"] else []
        except Exception:
            m_keys = [post["media_key"]] if post["media_key"] else []
            
        for target in targets:
            platform_str = target["platform"]
            
            # Skip targets that succeeded on previous attempts to avoid duplicate posting
            if target["status"] == "published":
                logger.info(f"Target platform {platform_str} for post {post_id} already published. Skipping.")
                continue
                
            try:
                try:
                    platform_enum = Platform(platform_str)
                except ValueError:
                    platform_enum = platform_str
                    
                await publish_post_event(
                    post_id=post_id,
                    platform=platform_enum,
                    content=post["content"],
                    media_key=post["media_key"],
                    user_id=user_id,
                    media_keys=m_keys,
                    is_reel=post["is_reel"],
                    facebook_page_id=post.get("facebook_page_id")
                )
                
                await log_post_stage(
                    database, post_id, "orchestrator", "scheduled_event_published", "INFO",
                    f"Successfully published scheduled post event to posts.{platform_str}"
                )
            except Exception as e:
                logger.error(f"Failed to publish scheduled post {post_id} to {platform_str}: {e}")
                failed_publish = True
                last_error = str(e)
                
                await log_post_stage(
                    database, post_id, "orchestrator", "scheduled_publish_failed", "ERROR",
                    f"Failed to publish scheduled post event to {platform_str}: {e}"
                )
                # Update target status to failed
                update_target_query = PostTarget.update().where(
                    (PostTarget.c.post_id == post_id) & 
                    (PostTarget.c.platform == platform_str)
                ).values(status="failed")
                await database.execute(update_target_query)
        
        # 3. If RabbitMQ event publishing itself failed (e.g. RabbitMQ is down), reschedule retry
        if failed_publish:
            new_retry_count = (post["retry_count"] or 0) + 1
            if new_retry_count < 3:
                # Reschedule retry in 5 minutes (300 seconds)
                next_attempt = datetime.utcnow() + dt_module.timedelta(minutes=5)
                await database.execute(
                    Post.update().where(Post.c.id == post_id).values(
                        scheduler_status="scheduled",
                        retry_count=new_retry_count,
                        scheduled_at=next_attempt,
                        status=PostStatus.PENDING.value
                    )
                )
                
                # Reset only failed/pending target statuses back to pending so they will be retried
                await database.execute(
                    PostTarget.update().where(
                        (PostTarget.c.post_id == post_id) & 
                        (PostTarget.c.status != "published")
                    ).values(status="pending")
                )
                
                await log_post_stage(
                    database, post_id, "orchestrator", "retry_scheduled", "WARNING",
                    f"Scheduling retry {new_retry_count}/3 at {next_attempt} due to: {last_error}"
                )
                await create_notification(
                    user_id=user_id,
                    title="Scheduled post retry",
                    message=f"Scheduled post failed to publish. Retrying again in 5 minutes. (Attempt {new_retry_count}/3)",
                    notification_type="warning"
                )
            else:
                # Permanent failure
                await database.execute(
                    Post.update().where(Post.c.id == post_id).values(
                        scheduler_status="failed",
                        retry_count=new_retry_count,
                        status=PostStatus.FAILED.value
                    )
                )
                await create_notification(
                    user_id=user_id,
                    title="Scheduled post failed permanently",
                    message=f"Your scheduled post failed permanently after {new_retry_count} attempts: {last_error}",
                    notification_type="error"
                )
        else:
            logger.info(f"All events for scheduled post {post_id} published successfully to queues.")

    await asyncio.gather(*(process_claimed_post(post) for post in scheduled_posts))
