from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import db_settings

redis_instance = Redis(
    host=db_settings.REDIS_HOST,
    port=db_settings.REDIS_PORT,
    db=0,
    ssl=db_settings.REDIS_SSL,
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
    return bool(await redis_instance.exists(jti))


async def ping_redis() -> bool:
    """
    Check whether Redis is reachable.
    """
    try:
        ping_result = redis_instance.ping()
        if isinstance(ping_result, bool):
            return ping_result
        return bool(await ping_result)
    except RedisError:
        return False
