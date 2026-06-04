import asyncio
import logging

logger = logging.getLogger("common-db")

async def connect_db_with_retry(database, retries: int = 15, delay: float = 2.0):
    """
    Connects to the database with a retry mechanism to handle database startup delay.
    """
    attempt = 0
    while attempt < retries:
        try:
            await database.connect()
            logger.info("Successfully connected to the database.")
            return
        except Exception as e:
            attempt += 1
            if attempt >= retries:
                logger.error(f"Failed to connect to the database after {retries} attempts.")
                raise e
            logger.warning(
                f"Database connection attempt {attempt}/{retries} failed: {e}. "
                f"Retrying in {delay} seconds..."
            )
            await asyncio.sleep(delay)
