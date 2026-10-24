import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def rate_limit(scope: str, limit: int, window_seconds: int):
    async def check(request: Request):
        address = request.client.host if request.client else "unknown"
        key = (scope, address)
        now = time.monotonic()
        with _lock:
            events = _requests[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
            events.append(now)

    return check


auth_rate_limit = rate_limit("auth", 10, 60)
ai_rate_limit = rate_limit("ai", 20, 60)
