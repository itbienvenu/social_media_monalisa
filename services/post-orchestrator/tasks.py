import os
import asyncio
from arq import cron
from services.post_orchestrator.media import process_and_mix_media
from services.post_orchestrator.db import database, Post
import uuid
import json
from datetime import datetime
from logging import getLogger

logger = getLogger("post-orchestrator.tasks")

async def process_media_task(ctx, job_id: str, user_id: str, media_keys: list, audio_key: str = None, 
                            is_reel: bool = False, music_volume: float = 0.2, video_volume: float = 1.0, 
                            slideshow_duration: int = 10):
    """
    Background task to process media (FFmpeg compilation) without blocking the HTTP request.
    """
    try:
        logger.info(f"Starting media processing job {job_id} for user {user_id}")
        
        # Update job status to processing
        await update_job_status(job_id, "processing", 0, "Starting FFmpeg processing")
        
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
        
        # Update job status to completed
        if compiled_result:
            await update_job_status(job_id, "completed", 100, "Media processing completed successfully", 
                                   result=compiled_result)
            logger.info(f"Job {job_id} completed successfully")
        else:
            await update_job_status(job_id, "completed", 100, "No processing needed (already video format)")
            logger.info(f"Job {job_id} completed - no processing needed")
            
        return compiled_result
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await update_job_status(job_id, "failed", 0, f"Processing failed: {str(e)}")
        raise

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
