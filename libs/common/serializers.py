from pydantic import BaseModel, ConfigDict, field_validator
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

class Platform(str, Enum):
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"

class PostStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    SYNCED = "synced"

class PostBase(BaseModel):
    content: str
    media_key: Optional[str] = None
    media_keys: Optional[List[str]] = None
    platforms: List[Platform]
    is_reel: Optional[bool] = False
    facebook_page_id: Optional[str] = None

    @field_validator("media_keys")
    @classmethod
    def validate_media_keys(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for item in v:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("media_keys list must not contain nulls or empty strings")
        return v


class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    id: uuid.UUID
    status: PostStatus
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PlatformPostEvent(BaseModel):
    post_id: uuid.UUID
    platform: Platform
    content: str
    media_url: Optional[str] = None
    media_urls: Optional[List[str]] = None
    user_id: str
    is_reel: Optional[bool] = False
    
class AnalyticsSnapshot(BaseModel):
    post_id: uuid.UUID
    platform: Platform
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0
    timestamp: datetime
