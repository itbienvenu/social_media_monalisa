import os
from arq import create_pool
from arq.connections import RedisSettings

async def redis_pool(ctx=None):
    return await create_pool(RedisSettings(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        database=int(os.getenv('REDIS_DB', 0)),
    ))

class WorkerSettings:
    functions = ['services.post_orchestrator.tasks.process_media_task']
    on_startup = redis_pool
    redis_settings = RedisSettings(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        database=int(os.getenv('REDIS_DB', 0)),
    )
