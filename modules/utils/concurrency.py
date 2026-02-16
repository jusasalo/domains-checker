from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator, DefaultDict


class HostLimiter:
    def __init__(self, per_host_limit: int) -> None:
        self._per_host_limit = max(1, int(per_host_limit))
        self._host_semaphores: DefaultDict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self._per_host_limit)
        )

    @asynccontextmanager
    async def slot(self, host: str) -> AsyncIterator[None]:
        semaphore = self._host_semaphores[host]
        async with semaphore:
            yield
