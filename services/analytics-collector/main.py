import asyncio
import logging
from services.analytics_collector.models import database, Post, AnalyticsSnapshot
import datetime
import httpx
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics-collector")

POST_ORCHESTRATOR_URL = "http://post-orchestrator:8000"

async def collect_analytics():
    logger.info("Collecting analytics from all platforms...")
    try:
        # 1. Fetch all posts that have been successfully published, partially published, or synced
        query = Post.select().where(Post.c.status.in_(["published", "synced", "partial"]))
        posts = await database.fetch_all(query)
        logger.info(f"Found {len(posts)} active posts to update metrics.")
        
        async with httpx.AsyncClient() as client:
            for post in posts:
                post_id = post["id"]
                user_id = post["user_id"] or "anonymous"
                logger.info(f"Fetching metrics for post {post_id} (user: {user_id})")
                
                try:
                    resp = await client.get(
                        f"{POST_ORCHESTRATOR_URL}/posts/{post_id}/metrics",
                        params={"user_id": user_id},
                        timeout=10.0
                    )
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        platforms_metrics = data.get("platforms", {})
                        
                        for platform, metrics in platforms_metrics.items():
                            if not metrics:
                                continue
                            
                            # Insert snapshot to DB
                            snapshot_query = AnalyticsSnapshot.insert().values(
                                id=uuid.uuid4(),
                                post_id=post_id,
                                platform=platform,
                                likes=metrics.get("likes", 0),
                                shares=metrics.get("shares", 0),
                                comments=metrics.get("comments", 0),
                                views=metrics.get("views", 0),
                                timestamp=datetime.datetime.utcnow()
                            )
                            await database.execute(snapshot_query)
                            logger.info(f"Saved snapshot for post {post_id} on platform {platform}")
                    else:
                        logger.warning(f"Failed to fetch metrics for post {post_id}: HTTP {resp.status_code} - {resp.text}")
                except Exception as e:
                    logger.error(f"Error fetching metrics for post {post_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error during analytics collection: {e}")
        
    logger.info("Analytics collection complete.")

from libs.common.db import connect_db_with_retry

async def main():
    logger.info("Starting Analytics Collector...")
    await connect_db_with_retry(database)
    try:
        while True:
            await collect_analytics()
            await asyncio.sleep(60) # Run every minute for demo
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

