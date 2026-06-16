import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, Integer, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
import os
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

# Definition of posts table for JOIN queries
Post = Table(
    "posts",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("content", String),
    Column("media_key", String, nullable=True),
    Column("media_keys", String, nullable=True),
    Column("is_reel", Boolean, default=False),
    Column("status", String),
    Column("user_id", String, index=True, nullable=True),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
    Column("external_id", String, nullable=True, index=True),
    Column("platform", String, nullable=True),
)

# Same definition as collector
AnalyticsSnapshot = Table(
    "analytics_snapshots",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("post_id", UUID(as_uuid=True), index=True),
    Column("platform", String),
    Column("likes", Integer, default=0),
    Column("shares", Integer, default=0),
    Column("comments", Integer, default=0),
    Column("views", Integer, default=0),
    Column("timestamp", DateTime, default=datetime.datetime.utcnow),
)

