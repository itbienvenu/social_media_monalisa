from fastapi import APIRouter, HTTPException
from services.analytics_api.db import database, AnalyticsSnapshot
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
