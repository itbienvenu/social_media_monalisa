# pyright: ignore [reportMissingImport]
from fastapi.responses import JSONResponse, RedirectResponse, Response
import logging
import os
import datetime
from fastapi import FastAPI, HTTPException, status, Depends, Cookie
from contextlib import asynccontextmanager
import sqlalchemy
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt
from services.auth_service.db import database, metadata, users, oauth_states

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auth-service")

from libs.common.db import connect_db_with_retry

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Auth Service...")
    # Init DB
    await connect_db_with_retry(database)
    
    # Run migrations/alter table for new columns
    try:
        await database.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR;")
    except Exception as e:
        logger.warning(f"Failed to add full_name column to users: {e}")
        
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
    full_name: str | None = None

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None = None

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

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set HttpOnly; Secure; SameSite cookies for auth tokens"""
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    is_secure = BASE_URL.startswith("https://")
    samesite = "none" if is_secure else "lax"
    
    # Set access token cookie (30 minutes)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite=samesite,
        max_age=1800,  # 30 minutes
        path="/"
    )
    
    # Set refresh token cookie (60 days)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite=samesite,
        max_age=5184000,  # 60 days
        path="/"
    )

def clear_auth_cookies(response: Response):
    """Clear auth cookies"""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")

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
            is_active=True,
            full_name=user.full_name
        )
        await database.execute(query)
        logger.info(f"User registered successfully: {user.email}")
        return {"id": user_id, "email": user.email, "full_name": user.full_name}
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
        
        # Set HttpOnly cookies for security
        response = JSONResponse(content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        })
        set_auth_cookies(response, access_token, refresh_token)
        return response
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
    return {
        "id": user['id'],
        "email": user['email'],
        "full_name": user['full_name'] if 'full_name' in user else None
    }

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/refresh", response_model=Token)
async def refresh(request: RefreshRequest, refresh_token: str = Cookie(None)):
    try:
        # Use cookie refresh token if available, otherwise use request body
        token_to_use = refresh_token if refresh_token else request.refresh_token
        
        if not token_to_use:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing refresh token",
            )
            
        payload = jwt.decode(token_to_use, SECRET_KEY, algorithms=[ALGORITHM])
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
        
        # Set HttpOnly cookies for security
        response = JSONResponse(content={
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer"
        })
        set_auth_cookies(response, new_access, new_refresh)
        return response
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

@app.post("/logout")
async def logout():
    """Clear auth cookies"""
    response = JSONResponse(content={"message": "Logged out successfully"})
    clear_auth_cookies(response)
    return response

@app.get("/auth/google/url")
async def get_google_auth_url():
    import secrets
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    REDIRECT_URI = f"{BASE_URL}/auth/google/callback"
    MOCK_MODE = os.getenv("MOCK_MODE", "false")

    state = secrets.token_urlsafe(32)
    is_secure = BASE_URL.startswith("https://")
    samesite = "none" if is_secure else "lax"

    # Clean up old states (> 10 minutes)
    try:
        cleanup_query = oauth_states.delete().where(
            oauth_states.c.created_at < datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
        )
        await database.execute(cleanup_query)
        
        # Store state in DB
        insert_query = oauth_states.insert().values(state=state)
        await database.execute(insert_query)
    except Exception as e:
        logger.warning(f"Failed to manage oauth_states in database: {e}")

    if MOCK_MODE == "true":
        mock_callback_url = f"{BASE_URL}/auth/google/callback?code=mock_google_code&state={state}"
        response = JSONResponse(content={"url": mock_callback_url})
        response.set_cookie(
            key="oauth_state",
            value=state,
            httponly=True,
            secure=is_secure,
            samesite=samesite,
            max_age=600,
            path="/"
        )
        return response

    if not GOOGLE_CLIENT_ID:
        logger.error("Google OAuth client ID is missing and MOCK_MODE is not set to 'true'.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth configuration is missing on the server"
        )

    scopes = "openid email profile"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"state={state}&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    response = JSONResponse(content={"url": auth_url})
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=is_secure,
        samesite=samesite,
        max_age=600,
        path="/"
    )
    return response

@app.get("/auth/google/callback")
async def google_callback(
    code: str,
    state: str = None,
    oauth_state: str = Cookie(None)
):
    from fastapi import Request
    import httpx
    import uuid
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    REDIRECT_URI = f"{BASE_URL}/auth/google/callback"
    MOCK_MODE = os.getenv("MOCK_MODE", "false")

    # Verify state parameter to prevent login CSRF (checks database fallback or cookie)
    db_state_valid = False
    if state:
        try:
            query = oauth_states.select().where(oauth_states.c.state == state)
            db_state_record = await database.fetch_one(query)
            if db_state_record:
                db_state_valid = True
                # Clean up / delete the one-time state
                delete_query = oauth_states.delete().where(oauth_states.c.state == state)
                await database.execute(delete_query)
        except Exception as e:
            logger.warning(f"Error checking state in database: {e}")

    cookie_state_valid = bool(state and oauth_state and state == oauth_state)

    if not db_state_valid and not cookie_state_valid:
        logger.error(f"Google OAuth callback: state mismatch. state={state}, oauth_state={oauth_state}")
        response = RedirectResponse(url=f"{FRONTEND_URL}/login?error=Invalid state parameter")
        response.delete_cookie(key="oauth_state", path="/")
        return response

    email = None
    google_name = None

    if MOCK_MODE == "true":
        email = "mock_google_user@example.com"
        google_name = "Mock Google User"
        logger.info(f"Mocking Google Auth Callback for email: {email}")
    else:
        if code == "mock_google_code":
            logger.error("Attempted to use mock auth code when MOCK_MODE is not enabled.")
            response = RedirectResponse(url=f"{FRONTEND_URL}/login?error=Invalid authorization code")
            response.delete_cookie(key="oauth_state", path="/")
            return response
            
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.error("Google OAuth credentials are missing and MOCK_MODE is not enabled.")
            response = RedirectResponse(url=f"{FRONTEND_URL}/login?error=Google OAuth is not configured on the server")
            response.delete_cookie(key="oauth_state", path="/")
            return response
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(token_url, data=data)
                resp.raise_for_status()
                token_data = resp.json()
                access_token = token_data.get("access_token")
                
                userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_resp = await client.get(userinfo_url, headers=headers)
                userinfo_resp.raise_for_status()
                userinfo = userinfo_resp.json()
                email = userinfo.get("email")
                google_name = userinfo.get("name")
            except Exception as e:
                logger.error(f"Failed to complete Google OAuth exchange: {e}")
                response = RedirectResponse(url=f"{FRONTEND_URL}/login?error=Google auth failed")
                response.delete_cookie(key="oauth_state", path="/")
                return response

    if not email:
        response = RedirectResponse(url=f"{FRONTEND_URL}/login?error=Failed to retrieve email from Google")
        response.delete_cookie(key="oauth_state", path="/")
        return response

    query = users.select().where(users.c.email == email)
    db_user = await database.fetch_one(query)
    
    user_id = None
    if not db_user:
        user_id = str(uuid.uuid4())
        import secrets
        dummy_password = secrets.token_hex(16)
        hashed_pw = get_password_hash(dummy_password)
        
        insert_query = users.insert().values(
            id=user_id,
            email=email,
            hashed_password=hashed_pw,
            is_active=True,
            full_name=google_name
        )
        await database.execute(insert_query)
        logger.info(f"New user registered via Google: {email}")
    else:
        user_id = db_user['id']
        logger.info(f"Existing user logged in via Google: {email}")

    access_token = create_access_token(data={"sub": user_id, "email": email})
    refresh_token = create_refresh_token(data={"sub": user_id, "email": email})

    # Set HttpOnly cookies and redirect to dashboard without tokens in URL
    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    response.delete_cookie(key="oauth_state", path="/")
    set_auth_cookies(response, access_token, refresh_token)
    return response
