# pyright: ignore [reportMissingImport]
from fastapi.responses import JSONResponse
import logging
import os
import datetime
from fastapi import FastAPI, HTTPException, status, Depends
from contextlib import asynccontextmanager
import sqlalchemy
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt
from services.auth_service.db import database, metadata, users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auth-service")

from libs.common.db import connect_db_with_retry

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Auth Service...")
    # Init DB
    await connect_db_with_retry(database)
    
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
    except Exception as e:
        logger.warning(f"Table creation skipped or already completed: {e}")
    yield
    await database.disconnect()

# Security config
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserProfile(BaseModel):
    id: str
    email: str

import hashlib

def verify_password_versioned(plain_password: str, hashed_password: str) -> tuple[bool, bool]:
    """
    Verifies a password against the hash.
    Returns (is_valid, needs_upgrade).
    """
    # 1. Try the new scheme: bcrypt of sha256
    pw_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    try:
        if pwd_context.verify(pw_hash, hashed_password):
            return True, False
    except Exception:
        pass

    # 2. Try the old scheme: direct bcrypt of raw password
    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True, True
    except Exception:
        pass

    return False, False

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return verify_password_versioned(plain_password, hashed_password)[0]

def get_password_hash(password: str) -> str:
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd_context.hash(pw_hash)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

app = FastAPI(title="Auth Service", lifespan=lifespan)

@app.post("/register", response_model=UserProfile)
async def register(user: UserCreate):
    try:
        query = users.select().where(users.c.email == user.email)
        existing_user = await database.fetch_one(query)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        import uuid
        user_id = str(uuid.uuid4())
        hashed_pw = get_password_hash(user.password)
        
        query = users.insert().values(
            id=user_id,
            email=user.email,
            hashed_password=hashed_pw,
            is_active=True
        )
        await database.execute(query)
        logger.info(f"User registered successfully: {user.email}")
        return {"id": user_id, "email": user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/login", response_model=Token)
async def login(user: UserCreate):
    try:
        query = users.select().where(users.c.email == user.email)
        db_user = await database.fetch_one(query)
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        is_valid, needs_upgrade = verify_password_versioned(user.password, db_user['hashed_password'])
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if needs_upgrade:
            # Upgrade password to the new scheme in the database
            new_hash = get_password_hash(user.password)
            update_query = users.update().where(users.c.id == db_user['id']).values(hashed_password=new_hash)
            await database.execute(update_query)
            logger.info(f"Password upgraded to new scheme for user: {user.email}")
            
        access_token = create_access_token(data={"sub": db_user['id'], "email": db_user['email']})
        refresh_token = create_refresh_token(data={"sub": db_user['id'], "email": db_user['email']})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/me")
async def read_users_me(token: str):
    # Simplified verification for internal use or validation
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    query = users.select().where(users.c.id == user_id)
    user = await database.fetch_one(query)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user['id'], "email": user['email']}

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/refresh", response_model=Token)
async def refresh(request: RefreshRequest):
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload",
            )
        query = users.select().where(users.c.id == user_id)
        db_user = await database.fetch_one(query)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        new_access = create_access_token(data={"sub": user_id, "email": email})
        new_refresh = create_refresh_token(data={"sub": user_id, "email": email})
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer"
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

@app.get("/health")
async def health():
    try:
        await database.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "detail": "Database connection error"}
        )
