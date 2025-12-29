import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import os
from libs.common.serializers import PostStatus, Platform
import uuid
import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

database = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

Post = Table(
    "posts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("content", String),
    Column("media_key", String, nullable=True),
    Column("status", String, default=PostStatus.PENDING.value),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
)

PostTarget = Table(
    "post_targets",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("post_id", UUID(as_uuid=True), ForeignKey("posts.id")),
    Column("platform", String),
    Column("status", String, default="pending"),
    Column("external_id", String, nullable=True),
)
