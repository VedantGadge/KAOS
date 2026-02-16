import time
import functools
import random
from shared.logger import logger

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    """
    Decorator to retry a function call with exponential backoff code.
    
    Args:
        retries (int): Number of times to retry before giving up.
        backoff_in_seconds (int): Initial delay in seconds.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        logger.error(f"❌ All {retries} retries failed for {func.__name__}: {e}")
                        raise e
                    
                    sleep = (backoff_in_seconds * 2 ** x) + random.uniform(0, 1)
                    logger.warning(f"⚠️ {func.__name__} failed: {e}. Retrying in {sleep:.2f}s ({x+1}/{retries})...")
                    time.sleep(sleep)
                    x += 1
        return wrapper
    return decorator
