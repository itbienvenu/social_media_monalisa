import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import os
import uuid
import datetime

# We probably want to share the main DB or have a separate one. 
# For monorepo simplicity, we assume one shared Postgres instance but distinct tables.
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

# In a real microservice, this would be its own DB. 
# Here we namespace it or just use a distinct table.
SocialCredential = Table(
    "facebook_credentials",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", String, index=True), # User ID from the main auth system (API Gateway)
    Column("platform", String, default="facebook"),
    Column("access_token", String), # Encrypted in real world
    Column("page_id", String, nullable=True), # Deprecated in favor of SocialTargets
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
)

SocialTarget = Table(
    "facebook_targets",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", String, index=True),
    Column("target_id", String), # Page ID or Group ID
    Column("target_name", String),
    Column("target_type", String), # 'page' or 'group'
    Column("access_token", String), # Page Access Token
    Column("platform", String, default="facebook"),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
)
