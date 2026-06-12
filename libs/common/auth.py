from typing import Optional
from fastapi import Header, HTTPException, status, Cookie
import logging

logger = logging.getLogger("auth")

async def verify_token(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> dict:
    # Debug incoming tokens
    print(f"VERIFY TOKEN: access_token_cookie={access_token}, authorization_header={authorization}", flush=True)
    
    # First try to get token from HttpOnly cookie
    token = access_token
    
    # Fall back to Authorization header if cookie not present
    if not token and authorization:
        scheme, _, header_token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = header_token
    
    if not token:
        print("VERIFY TOKEN: No token found in cookies or authorization header", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing authentication credentials"
        )

    # Real JWT Verification
    from jose import jwt, JWTError
    import os
    
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
    ALGORITHM = "HS256"
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError:
        logger.debug("Token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
