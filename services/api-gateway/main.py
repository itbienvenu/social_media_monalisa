from fastapi import FastAPI
from libs.common.logger import setup_logger

logger = setup_logger("api-gateway")

app = FastAPI(title="Social Media Platform API Gateway")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "api-gateway"}

# Import routers after app creation to avoid circular deps if any
from services.api_gateway import router
app.include_router(router.router)
