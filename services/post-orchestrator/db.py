import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import os
from libs.common.serializers import PostStatus, Platform
import uuid
import datetime

import urllib.parse

DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_platform")

password_encoded = urllib.parse.quote_plus(DB_PASSWORD)
user_encoded = urllib.parse.quote_plus(DB_USER)

DATABASE_URL = f"postgresql://{user_encoded}:{password_encoded}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
database = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

Post = Table(
    "posts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("content", String),
    Column("media_key", String, nullable=True),
    Column("media_keys", String, nullable=True),
    Column("is_reel", sqlalchemy.Boolean, default=False, server_default="false"),
    Column("status", String, default=PostStatus.PENDING.value),
    Column("user_id", String, index=True, nullable=True),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
    # New columns for historical sync
    Column("external_id", String, nullable=True, index=True),
    Column("platform", String, nullable=True),
    UniqueConstraint("user_id", "platform", "external_id", name="uq_user_platform_external_post"),
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

PostLog = Table(
    "post_logs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("post_id", UUID(as_uuid=True), nullable=True),
    Column("platform", String),
    Column("stage", String),
    Column("status", String),
    Column("message", String, nullable=True),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
)
