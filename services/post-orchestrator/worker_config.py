import os
from arq import create_pool
from arq.connections import RedisSettings

async def startup(ctx):
    # Connect DB
    from services.post_orchestrator.db import database
    from libs.common.db import connect_db_with_retry
    await connect_db_with_retry(database)
    
    # Connect RabbitMQ
    from services.post_orchestrator.events import mq
    await mq.connect()
    
    # Put redis pool in ctx
    ctx['redis'] = await create_pool(RedisSettings(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        database=int(os.getenv('REDIS_DB', 0)),
    ))

async def shutdown(ctx):
    # Disconnect DB
    from services.post_orchestrator.db import database
    try:
        await database.disconnect()
    except Exception:
        pass
        
    # Disconnect RabbitMQ
    from services.post_orchestrator.events import mq
    try:
        await mq.disconnect()
    except Exception:
        pass
        
    # Close Redis
    if 'redis' in ctx:
        try:
            await ctx['redis'].close()
        except Exception:
            pass

from arq import cron

class WorkerSettings:
    functions = [
        'services.post_orchestrator.tasks.process_media_task',
        'services.post_orchestrator.tasks.check_scheduled_posts'
    ]
    cron_jobs = [
        cron('services.post_orchestrator.tasks.check_scheduled_posts', second={0, 15, 30, 45})
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        database=int(os.getenv('REDIS_DB', 0)),
    )
