from redis.asyncio import Redis

from src.core.config import redis_settings


redis_instance = Redis(
    host=redis_settings.redis_host,
    port=redis_settings.redis_port,
    db=0,
)

async def add_jti_to_blacklist(jti: str) -> None:
    """
    Add a JTI of a token to the blacklist
    """
    await redis_instance.set(jti, "blacklisted")


async def is_jti_blacklisted(jti: str) -> bool:
    """
    Check if a JTI is in the blacklist
    """
    return await redis_instance.exists(jti)
   
