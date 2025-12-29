import databases
import sqlalchemy
from sqlalchemy import Table, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import os
import uuid
import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

database = databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

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
