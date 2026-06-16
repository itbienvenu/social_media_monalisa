from fastapi import APIRouter, HTTPException
from services.analytics_api.db import database, AnalyticsSnapshot, Post
from libs.common.serializers import AnalyticsSnapshot as AnalyticsSnapshotModel
import uuid
from typing import List

router = APIRouter()

@router.get("/analytics/posts/{post_id}", response_model=List[AnalyticsSnapshotModel])
async def get_post_analytics(post_id: uuid.UUID):
    query = AnalyticsSnapshot.select().where(AnalyticsSnapshot.c.post_id == post_id)
    results = await database.fetch_all(query)
    return results

@router.get("/analytics/platforms/{platform}", response_model=List[AnalyticsSnapshotModel])
async def get_platform_analytics(platform: str):
    query = AnalyticsSnapshot.select().where(AnalyticsSnapshot.c.platform == platform)
    results = await database.fetch_all(query)
    return results

@router.get("/analytics/summary")
async def get_analytics_summary(user_id: str):
    """
    Fetches the total and average engagement metrics across all posts for a user.
    Uses a subquery to extract only the latest snapshot per post and platform.
    """
    query = """
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (post_id, platform) post_id, platform, likes, comments, shares, views, timestamp
            FROM analytics_snapshots
            ORDER BY post_id, platform, timestamp DESC
        )
        SELECT 
            COALESCE(SUM(s.likes), 0) as total_likes,
            COALESCE(SUM(s.comments), 0) as total_comments,
            COALESCE(SUM(s.shares), 0) as total_shares,
            COALESCE(SUM(s.views), 0) as total_views,
            COUNT(DISTINCT p.id) as total_posts
        FROM posts p
        LEFT JOIN latest_snapshots s ON p.id = s.post_id
        WHERE p.user_id = :user_id
    """
    try:
        row = await database.fetch_one(query=query, values={"user_id": user_id})
        if not row:
            return {
                "total_likes": 0, "total_comments": 0, "total_shares": 0, "total_views": 0, "total_posts": 0
            }
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation error: {e}")

@router.get("/analytics/content-performance")
async def get_content_performance(user_id: str):
    """
    Compares metrics (likes, views, comments) of Reels/Videos vs Standard Feed Posts.
    """
    query = """
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (post_id, platform) post_id, platform, likes, comments, shares, views, timestamp
            FROM analytics_snapshots
            ORDER BY post_id, platform, timestamp DESC
        )
        SELECT 
            p.is_reel,
            COALESCE(AVG(s.likes), 0) as avg_likes,
            COALESCE(AVG(s.comments), 0) as avg_comments,
            COALESCE(AVG(s.shares), 0) as avg_shares,
            COALESCE(AVG(s.views), 0) as avg_views,
            COUNT(DISTINCT p.id) as post_count
        FROM posts p
        LEFT JOIN latest_snapshots s ON p.id = s.post_id
        WHERE p.user_id = :user_id
        GROUP BY p.is_reel
    """
    try:
        results = await database.fetch_all(query=query, values={"user_id": user_id})
        performance = []
        for r in results:
            performance.append({
                "format": "Reel" if r["is_reel"] else "Standard Post",
                "avg_likes": float(r["avg_likes"]),
                "avg_comments": float(r["avg_comments"]),
                "avg_shares": float(r["avg_shares"]),
                "avg_views": float(r["avg_views"]),
                "post_count": r["post_count"]
            })
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation error: {e}")

@router.get("/analytics/peak-times")
async def get_peak_times(user_id: str):
    """
    Correlates post publication hour and day of week with engagement rate
    to find optimal times.
    """
    query = """
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (post_id, platform) post_id, platform, likes, comments, shares, views
            FROM analytics_snapshots
            ORDER BY post_id, platform, timestamp DESC
        )
        SELECT 
            EXTRACT(DOW FROM p.created_at) as day_of_week,
            EXTRACT(HOUR FROM p.created_at) as hour_of_day,
            COALESCE(AVG(s.likes + s.comments + s.shares), 0) as avg_engagement,
            COUNT(DISTINCT p.id) as post_count
        FROM posts p
        JOIN latest_snapshots s ON p.id = s.post_id
        WHERE p.user_id = :user_id
        GROUP BY EXTRACT(DOW FROM p.created_at), EXTRACT(HOUR FROM p.created_at)
        ORDER BY avg_engagement DESC
    """
    try:
        results = await database.fetch_all(query=query, values={"user_id": user_id})
        return [
            {
                "day_of_week": int(r["day_of_week"]),
                "hour_of_day": int(r["hour_of_day"]),
                "avg_engagement": float(r["avg_engagement"]),
                "post_count": r["post_count"]
            }
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation error: {e}")

@router.get("/analytics/trends")
async def get_historical_trends(user_id: str):
    """
    Calculates the 30-day time-series analytics (daily totals).
    """
    query = """
        WITH daily_snapshots AS (
            SELECT DISTINCT ON (DATE(timestamp), post_id, platform) 
                DATE(timestamp) as date,
                post_id,
                platform,
                likes,
                comments,
                shares,
                views
            FROM analytics_snapshots
            ORDER BY DATE(timestamp), post_id, platform, timestamp DESC
        )
        SELECT 
            d.date,
            COALESCE(SUM(d.likes), 0) as total_likes,
            COALESCE(SUM(d.comments), 0) as total_comments,
            COALESCE(SUM(d.shares), 0) as total_shares,
            COALESCE(SUM(d.views), 0) as total_views
        FROM daily_snapshots d
        JOIN posts p ON d.post_id = p.id
        WHERE p.user_id = :user_id
        GROUP BY d.date
        ORDER BY d.date ASC
        LIMIT 30
    """
    try:
        results = await database.fetch_all(query=query, values={"user_id": user_id})
        return [
            {
                "date": str(r["date"]),
                "likes": int(r["total_likes"]),
                "comments": int(r["total_comments"]),
                "shares": int(r["total_shares"]),
                "views": int(r["total_views"])
            }
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation error: {e}")

