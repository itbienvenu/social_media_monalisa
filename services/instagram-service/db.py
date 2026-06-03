import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, DateTime
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

# Just like FB, we store the 'Target' (The specific Instagram Business Account)
SocialTarget = Table(
    "instagram_targets",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", String, index=True),
    Column("target_id", String), # Instagram Account ID
    Column("target_name", String),
    Column("access_token", String), # User Access Token (IG uses the FB User token + Page permissions)
    Column("page_id", String), # The FB Page ID this IG account is connected to
    Column("platform", String, default="instagram"),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
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
