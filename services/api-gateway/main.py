from fastapi import FastAPI
from libs.common.logger import setup_logger

logger = setup_logger("api-gateway")

app = FastAPI(title="Social Media Platform API Gateway")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("DEBUG: API Gateway CORS initialized with allow_origins=['*']")



@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "api-gateway"}

# Import routers after app creation to avoid circular deps if any
from services.api_gateway import router
app.include_router(router.router)
