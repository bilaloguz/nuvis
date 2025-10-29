import random
import time
from typing import Callable, Type, Tuple


def exponential_backoff_delays(
    retries: int,
    base: float = 0.2,
    factor: float = 2.0,
    jitter: Tuple[float, float] = (0.1, 0.4),
    max_delay: float = 10.0,
):
    """Generate delay sequence with exponential backoff and jitter (seconds)."""
    delay = base
    for _ in range(retries):
        low, high = jitter
        yield min(delay + random.uniform(low, high), max_delay)
        delay *= factor


def retry_with_backoff(
    exceptions: Tuple[Type[BaseException], ...],
    retries: int = 5,
    base: float = 0.2,
    factor: float = 2.0,
    jitter: Tuple[float, float] = (0.1, 0.4),
    max_delay: float = 10.0,
):
    """Decorator to retry a function with exponential backoff and jitter."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            last_exc = None
            for delay in exponential_backoff_delays(retries, base, factor, jitter, max_delay):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    time.sleep(delay)
            # Final attempt
            return func(*args, **kwargs)
        return wrapper
    return decorator
