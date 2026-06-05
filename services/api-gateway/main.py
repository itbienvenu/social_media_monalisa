from fastapi import FastAPI
from libs.common.logger import setup_logger

logger = setup_logger("api-gateway")

app = FastAPI(title="Social Media Platform API Gateway")

import os
from fastapi.middleware.cors import CORSMiddleware

# Define allowed CORS origins (localhost dev + ngrok/deployed frontend)
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_base_url = os.getenv("BASE_URL")
if env_base_url:
    allowed_origins.append(env_base_url.rstrip("/"))

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url.rstrip("/"))

# Allow configured custom origins via a comma-separated list
custom_origins = os.getenv("ALLOWED_ORIGINS")
if custom_origins:
    for origin in custom_origins.split(","):
        allowed_origins.append(origin.strip().rstrip("/"))

# Ensure unique origins in the list
allowed_origins = list(set(allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|.*\.amazonaws\.com|.*\.ngrok-free\.dev)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"DEBUG: API Gateway CORS initialized with allowed_origins={allowed_origins}")



@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "api-gateway"}

# Import routers after app creation to avoid circular deps if any
from services.api_gateway import router
app.include_router(router.router)
