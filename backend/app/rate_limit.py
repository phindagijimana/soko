"""Small in-memory rate limiting helpers for the MVP and pilot phase.

A production deployment should eventually swap this for a shared store such as
Redis so limits work across multiple application instances.
"""


from collections import defaultdict, deque
from time import time
from fastapi import HTTPException

from .settings import settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque] = defaultdict(deque)

    def clear(self) -> None:
        self._buckets.clear()

    def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        now = time()
        bucket = self._buckets[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= max_requests:
            raise HTTPException(status_code=429, detail='Too many requests. Please try again later.')
        bucket.append(now)


rate_limiter = InMemoryRateLimiter()


def rate_limit_for_path(path: str) -> int:
    if path.startswith('/auth/'):
        return settings.auth_rate_limit_max_requests
    if path.startswith('/images/'):
        return settings.upload_rate_limit_max_requests
    return settings.rate_limit_max_requests
