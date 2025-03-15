"""
Logic:
- Provides utility functions for the Todo app
- Includes retry mechanism with exponential backoff for API operations
"""

import time
import random
from functools import wraps

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    """
    Input: number of retries and backoff time
    Process: Retries function with exponential backoff
    Output: Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise e
                    sleep_time = (backoff_in_seconds * 2 ** x) + (random.random() * 0.1)
                    # Reduce sleep time for faster retries while maintaining exponential backoff
                    time.sleep(sleep_time / 2)
                    x += 1
        return wrapper
    return decorator 