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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Auth Service...")
    # Init DB
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    yield
    await database.disconnect()

# Security config
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfile(BaseModel):
    id: str
    email: str

import hashlib

def verify_password(plain_password, hashed_password):
    pw_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return pwd_context.verify(pw_hash, hashed_password)

def get_password_hash(password):
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd_context.hash(pw_hash)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
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
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/login", response_model=Token)
async def login(user: UserCreate):
    try:
        query = users.select().where(users.c.email == user.email)
        db_user = await database.fetch_one(query)
        
        if not db_user or not verify_password(user.password, db_user['hashed_password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = create_access_token(data={"sub": db_user['id'], "email": db_user['email']})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
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

@app.get("/health")
async def health():
    try:
        await database.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "database": "disconnected", "detail": str(e)}
