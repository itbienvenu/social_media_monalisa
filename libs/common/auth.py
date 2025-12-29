from typing import Optional
from fastapi import Header, HTTPException, status

async def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """
    Mock JWT verification.
    Expects 'Bearer mock-token'.
    """
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
    
    if token != "mock-token":
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Token"
        )
            
    return {"user_id": "test-user", "role": "admin"}
