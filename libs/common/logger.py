import logging
import sys
import uuid
import datetime
from typing import Any

def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

async def log_post_stage(database: Any, post_id: Any, platform: str, stage: str, status: str, message: str = None):
    """
    Log a post lifecycle transition stage to the shared post_logs database table
    and also log it to the local system logger.
    """
    sys_logger = logging.getLogger(platform)
    log_msg = f"[POST_STAGE] Post: {post_id} | Stage: {stage} | Status: {status} | Message: {message or ''}"
    if status.upper() == "ERROR":
        sys_logger.error(log_msg)
    elif status.upper() == "WARNING":
        sys_logger.warning(log_msg)
    else:
        sys_logger.info(log_msg)

    # Developer/local mode console highlighting
    import os
    if os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes"):
        color_map = {
            "INFO": "\033[92m",    # Green
            "WARNING": "\033[93m", # Yellow
            "ERROR": "\033[91m",   # Red
            "DEBUG": "\033[94m"    # Blue
        }
        reset_color = "\033[0m"
        bold = "\033[1m"
        
        emoji_map = {
            "post_created": "📝",
            "event_published": "📤",
            "event_received": "📥",
            "downloading_media": "⏳",
            "media_downloaded": "💾",
            "media_download_failed": "⚠️",
            "posting_to_platform": "🚀",
            "platform_success": "✅",
            "platform_failed": "❌",
            "no_page_target": "🚫"
        }
        
        emoji = emoji_map.get(stage, "🔔")
        color = color_map.get(status.upper(), "")
        
        dev_msg = f"{color}{bold}[LIFECYCLE] {emoji} {platform.upper()} | Stage: {stage} | Status: {status} | Post: {post_id}{reset_color}"
        if message:
            dev_msg += f"\n  Detail: {message}"
        
        print(dev_msg, file=sys.stdout, flush=True)
        
    try:
        p_uuid = uuid.UUID(str(post_id)) if post_id else None
        
        query = """
            INSERT INTO post_logs (id, post_id, platform, stage, status, message, created_at)
            VALUES (:id, :post_id, :platform, :stage, :status, :message, :created_at)
        """
        await database.execute(
            query=query,
            values={
                "id": uuid.uuid4(),
                "post_id": p_uuid,
                "platform": platform,
                "stage": stage,
                "status": status,
                "message": message,
                "created_at": datetime.datetime.utcnow()
            }
        )
    except Exception as e:
        sys_logger.error(f"Failed to write to database post_logs table: {e}")
