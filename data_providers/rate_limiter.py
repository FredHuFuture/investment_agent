from __future__ import annotations

import asyncio
import collections


class AsyncRateLimiter:
    """Token-bucket rate limiter for async code.

    Tracks a sliding window of call timestamps.  If ``max_calls`` calls have
    already occurred within ``period_seconds``, :meth:`acquire` sleeps until
    the oldest call falls outside the window before allowing the next call.

    Usage::

        limiter = AsyncRateLimiter(max_calls=5, period_seconds=1.0)

        async with limiter:
            response = await some_api_call()

    The limiter is safe to share across coroutines — an internal
    :class:`asyncio.Lock` serialises access so the window accounting stays
    consistent.  Sleeping inside the lock means waiters queue up in order,
    which naturally spaces calls out without exceeding the configured rate.
    """

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be > 0")
        self._max_calls = max_calls
        self._period = period_seconds
        self._calls: collections.deque[float] = collections.deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a call slot is available, then claim it."""
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()

            # Drop timestamps older than the current window.
            while self._calls and now - self._calls[0] >= self._period:
                self._calls.popleft()

            if len(self._calls) >= self._max_calls:
                # Oldest call is still inside the window — wait for it to expire.
                wait = self._period - (now - self._calls[0])
                if wait > 0:
                    await asyncio.sleep(wait)
                # Re-sweep after waking up.
                now = loop.time()
                while self._calls and now - self._calls[0] >= self._period:
                    self._calls.popleft()

            self._calls.append(loop.time())

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
