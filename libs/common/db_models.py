import sqlalchemy
from sqlalchemy import Table, Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

shared_metadata = sqlalchemy.MetaData()

SocialAccount = Table(
    "social_accounts",
    shared_metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", String, index=True, nullable=False),
    Column("platform", String, nullable=False),
    Column("platform_user_id", String, nullable=False),
    Column("account_name", String, nullable=False),
    Column("username", String, nullable=True),
    Column("display_name", String, nullable=True),
    Column("profile_picture", String, nullable=True),
    Column("is_active", sqlalchemy.Boolean, default=True, server_default="true"),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
    UniqueConstraint("user_id", "platform", "platform_user_id", name="uq_user_platform_platform_user"),
)

OAuthToken = Table(
    "oauth_tokens",
    shared_metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("account_id", UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
    Column("access_token", String, nullable=False),
    Column("refresh_token", String, nullable=True),
    Column("expires_at", DateTime, nullable=True),
    Column("refresh_expires_at", DateTime, nullable=True),
    Column("scopes", String, nullable=True),
    Column("updated_at", DateTime, default=datetime.datetime.utcnow),
)

SocialTarget = Table(
    "social_targets",
    shared_metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("account_id", UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
    Column("target_id", String, nullable=False),
    Column("target_name", String, nullable=False),
    Column("target_type", String, nullable=False),
    Column("access_token", String, nullable=True),
    Column("platform", String, nullable=False),
    Column("is_preferred", sqlalchemy.Boolean, default=False, server_default="false"),
    Column("profile_picture", String, nullable=True),
    Column("created_at", DateTime, default=datetime.datetime.utcnow),
)

TokenRefreshMetadata = Table(
    "token_refresh_metadata",
    shared_metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("account_id", UUID(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
    Column("last_refreshed_at", DateTime, nullable=True),
    Column("refresh_status", String, nullable=False),
    Column("error_message", String, nullable=True),
)
