from pydantic import BaseModel
from typing import Optional, List

class ConnectResponse(BaseModel):
    url: str

class CredentialResponse(BaseModel):
    connected: bool
    platform: str
    id: Optional[str] = None

class DeleteCredentialsResponse(BaseModel):
    status: str

class FacebookPostResponse(BaseModel):
    original_id: str
    content: str
    created_at: Optional[str] = None
    platform: str
    permalink: Optional[str] = None

class FacebookMetricsResponse(BaseModel):
    likes: int
    comments: int
    shares: int
    views: int
    video_status: Optional[str] = None
    video_progress: Optional[int] = None
    permalink: Optional[str] = None
