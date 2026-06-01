from typing import Optional
from fastapi import Header, HTTPException, status

async def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing Authorization Header"
        )
    
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Authorization Scheme"
        )

    # Real JWT Verification
    from jose import jwt, JWTError
    import os
    
    # DEBUG PRINT
    # print(f"DEBUG: Received token: {token[:20]}...") 
    
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
    ALGORITHM = "HS256"
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"user_id": user_id, "email": payload.get("email")}
    except JWTError as e:
        print(f"DEBUG: Token verification failed: {e}")
        # print(f"DEBUG: SECRET_KEY used: {SECRET_KEY[:4]}***") # Optional: check key prefix
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
