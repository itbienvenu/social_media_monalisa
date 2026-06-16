from fastapi import FastAPI
from services.analytics_api.db import database, metadata
import sqlalchemy
import logging
from contextlib import asynccontextmanager

from libs.common.db import connect_db_with_retry

logger = logging.getLogger("analytics-api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db_with_retry(database)
    
    # Auto-create tables on startup
    engine = sqlalchemy.create_engine(str(database.url))
    try:
        metadata.create_all(engine)
        logger.info("Database tables initialized successfully in analytics-api")
    except Exception as e:
        logger.warning(f"Database table initialization skipped or failed: {e}")
        
    yield
    await database.disconnect()

app = FastAPI(title="Analytics API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "analytics-api"}

from services.analytics_api import router
app.include_router(router.router)

