import os
from typing import Optional

from redis import Redis
from rq import Queue


def get_redis() -> Redis:
    """Return a Redis client using REDIS_URL or localhost default."""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Use raw bytes (decode_responses=False) for full RQ compatibility
    return Redis.from_url(url, decode_responses=False)


def get_queue(name: Optional[str] = None) -> Queue:
    """Return an RQ Queue bound to our Redis client."""
    return Queue(name or "default", connection=get_redis())


def acquire_lock(key: str, ttl_seconds: int) -> bool:
    """Best-effort SETNX lock with TTL. Returns True if acquired."""
    r = get_redis()
    # Use NX to set if not exists; EX for seconds TTL
    return bool(r.set(name=key, value="1", nx=True, ex=ttl_seconds))


def release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:
        pass


# Simple semaphore using Redis counter
_DEF_SEM_TTL = 3600


def semaphore_key(name: str) -> str:
    return f"sem:{name}:count"


def semaphore_try_acquire(name: str, limit: int, ttl_seconds: int = _DEF_SEM_TTL) -> bool:
    r = get_redis()
    key = semaphore_key(name)
    pipe = r.pipeline()
    while True:
        try:
            pipe.watch(key)
            current = r.get(key)
            current_val = int(current) if current is not None else 0
            if current_val >= max(1, limit):
                pipe.unwatch()
                return False
            pipe.multi()
            pipe.incr(key, 1)
            if current is None:
                pipe.expire(key, ttl_seconds)
            pipe.execute()
            return True
        except Exception:
            try:
                pipe.reset()
            except Exception:
                pass
            return False
        finally:
            try:
                pipe.reset()
            except Exception:
                pass


def semaphore_release(name: str) -> None:
    try:
        r = get_redis()
        key = semaphore_key(name)
        val = r.decr(key)
        if val <= 0:
            r.delete(key)
    except Exception:
        pass
