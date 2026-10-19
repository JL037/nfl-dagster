"""Rate limits for the Ask page: a cap per visitor (per minute and per hour) and one for the
whole site per day, so a script can't run up the Claude bill.

In memory only, and never the visitor's address: each address is reduced to a salted hash
(the salt is random per process, so a hash can't be matched to an address, or across
restarts). Entries are dropped once their window has passed; a restart forgets everything.
"""

import hashlib
import math
import secrets
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

MINUTE, HOUR, DAY = 60, 3600, 86400


@dataclass
class Decision:
    ok: bool
    retry_after: int = 0  # seconds until the next question would be allowed


class RateLimiter:
    def __init__(self, *, per_minute: int = 5, per_hour: int = 30, per_day_total: int = 500,
                 clock: Callable[[], float] = time.monotonic):
        self.per_minute, self.per_hour, self.per_day_total = per_minute, per_hour, per_day_total
        self.clock = clock
        self._salt = secrets.token_bytes(16)
        self.visitors: dict[str, deque[float]] = {}  # hashed visitor -> question times, last hour
        self.site: deque[float] = deque()  # every question's time, last day

    def _key(self, visitor: str) -> str:
        return hashlib.sha256(self._salt + visitor.encode()).hexdigest()

    def _forget_old(self, now: float) -> None:
        while self.site and self.site[0] <= now - DAY:
            self.site.popleft()
        for key in list(self.visitors):
            times = self.visitors[key]
            while times and times[0] <= now - HOUR:
                times.popleft()
            if not times:
                del self.visitors[key]

    def allow(self, visitor: str) -> Decision:
        """Count one question for `visitor` if it's within every limit."""
        now = self.clock()
        self._forget_old(now)
        times = self.visitors.get(self._key(visitor), deque())
        last_minute = [t for t in times if t > now - MINUTE]
        waits = []
        if len(last_minute) >= self.per_minute:
            waits.append(last_minute[-self.per_minute] + MINUTE - now)
        if len(times) >= self.per_hour:
            waits.append(times[-self.per_hour] + HOUR - now)
        if len(self.site) >= self.per_day_total:
            waits.append(self.site[-self.per_day_total] + DAY - now)
        if waits:
            return Decision(ok=False, retry_after=max(1, math.ceil(max(waits))))
        times.append(now)
        self.visitors[self._key(visitor)] = times
        self.site.append(now)
        return Decision(ok=True)
