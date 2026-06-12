import hmac
import hashlib
import time
import os

# Using MINIO_SECRET_KEY as the fallback signing key because it is shared
# across the relevant services in docker-compose.yml
SIGNING_KEY = os.getenv("MINIO_SECRET_KEY", "minioadminpassword")

def sign_url_path(bucket: str, key: str, expires_in: int = 86400) -> tuple[int, str]:
    """
    Generates a signature and expiry timestamp for a bucket and key.
    Default expiry is 24 hours (86400 seconds).
    """
    exp = int(time.time()) + expires_in
    msg = f"{bucket}/{key}:{exp}".encode("utf-8")
    sig = hmac.new(SIGNING_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return exp, sig

def verify_url_path(bucket: str, key: str, exp_val: str | int, sig: str) -> bool:
    """
    Verifies the signature and expiration for a bucket and key.
    """
    try:
        exp = int(exp_val)
    except (ValueError, TypeError):
        return False
        
    # Check expiry
    if time.time() > exp:
        return False
        
    # Verify HMAC
    msg = f"{bucket}/{key}:{exp}".encode("utf-8")
    expected_sig = hmac.new(SIGNING_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected_sig, sig)
