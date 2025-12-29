import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request
from services.facebook_service.logic import post_to_facebook
from services.facebook_service.db import database, metadata, SocialCredential
from libs.common.messaging import MessageQueue
import sqlalchemy
from contextlib import asynccontextmanager
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facebook-service")

mq = MessageQueue("facebook-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    print(f"DEBUG: DATABASE_URL={database.url}", flush=True)
    engine = sqlalchemy.create_engine(str(database.url))
    metadata.create_all(engine)
    
    await database.connect()
    
    # Start Consumer Background Task
    consume_task = asyncio.create_task(consume_loop())
    
    yield
    
    consume_task.cancel()
    # await database.disconnect()

app = FastAPI(title="Facebook Service", lifespan=lifespan)

async def consume_loop():
    logger.info("Starting Facebook Service Consumer...")
    await mq.subscribe("posts.facebook", handle_post_event)
    while True:
        await asyncio.sleep(1)

async def handle_post_event(message: dict):
    logger.info(f"Received post event: {message}")
    post_id = message.get("post_id")
    content = message.get("content")
    # In a real system, the event should contain the user_id of the poster
    # For now, we might assume a default user or mock it from the message if we add it to the message schema
    # Let's assume the event sender (orchestrator) needs to be updated to send user_id.
    # For this iteration, I'll mock looking up the FIRST credential found or specific one.
    user_id = message.get("user_id", "test-user") 
    
    # Fetch token
    query = SocialCredential.select().where(SocialCredential.c.user_id == user_id)
    cred = await database.fetch_one(query)
    
    if cred:
        await post_to_facebook(post_id, content, cred['access_token'], cred['page_id'])
    else:
        logger.error(f"No credentials found for user {user_id}")
        await mq.publish("posts.facebook.failed", {"post_id": post_id, "reason": "no_credentials"})

# --- OAuth Endpoints ---

@app.post("/auth/connect")
async def connect_facebook(user_id: str):
    """
    Returns the URL to redirect the user to.
    """
    # MOCK implementation
    # Real: Return f"https://www.facebook.com/v18.0/dialog/oauth?client_id={APP_ID}..."
    return {"url": f"http://localhost:8000/auth/facebook/callback?code=mock_auth_code_for_{user_id}&state={user_id}"}

@app.get("/auth/callback")
async def facebook_callback(code: str, state: str):
    """
    Receives code, exchanges for token, stores it.
    State is used as user_id for simplicity here.
    """
    user_id = state
    # MOCK token exchange
    mock_token = f"EAAB_mock_token_for_{user_id}"
    mock_page_id = f"mock_page_{user_id}"
    
    # Store in DB
    query = SocialCredential.insert().values(
        id=uuid.uuid4(),
        user_id=user_id,
        platform="facebook",
        access_token=mock_token,
        page_id=mock_page_id
    )
    await database.execute(query)
    
    return {"status": "connected", "user_id": user_id}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
