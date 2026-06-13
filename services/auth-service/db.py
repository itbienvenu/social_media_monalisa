import databases
import sqlalchemy
import os
from urllib.parse import quote_plus

# Construct DATABASE_URL from individual components to handle special characters in password
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "social_platform")

# URL encode the password to safely handle special characters like '@'
encoded_password = quote_plus(DB_PASSWORD)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

import datetime

users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True),
    sqlalchemy.Column("full_name", sqlalchemy.String, nullable=True),
)

oauth_states = sqlalchemy.Table(
    "oauth_states",
    metadata,
    sqlalchemy.Column("state", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.datetime.utcnow),
)
