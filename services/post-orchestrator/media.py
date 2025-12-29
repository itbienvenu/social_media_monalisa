def generate_upload_url(filename: str) -> str:
    """
    Generates a mock pre-signed URL.
    """
    return f"https://mock-s3.bucket/upload/{filename}?token=mock-token"
