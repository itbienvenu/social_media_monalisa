from fastapi import FastAPI
from services.analytics_api.db import database
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.disconnect()

app = FastAPI(title="Analytics API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "analytics-api"}

from services.analytics_api import router
app.include_router(router.router)
