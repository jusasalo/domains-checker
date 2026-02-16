from __future__ import annotations

import asyncio
import time
from typing import Any, List, Optional

from modules.core.models import HTTPResult, HttpCheckConfig
from modules.utils.net import ms_to_seconds

try:
    import httpx as httpx_lib
except ImportError:  # pragma: no cover - optional dependency
    httpx_lib = None


async def run_http_check(
    domain: str,
    config: HttpCheckConfig,
    timeout_ms: int,
    retries: int,
    user_agent: str,
    client: Optional[Any] = None,
) -> HTTPResult:
    if httpx_lib is None:
        return HTTPResult(
            queried=True,
            reachable=False,
            error="httpx not installed. Run: pip install httpx",
        )

    timeout_s = ms_to_seconds(timeout_ms)
    max_attempts = max(1, retries + 1)
    errors: List[str] = []

    owns_client = client is None
    if owns_client:
        client = httpx_lib.AsyncClient(
            timeout=httpx_lib.Timeout(timeout_s),
            limits=httpx_lib.Limits(max_connections=20, max_keepalive_connections=20),
            follow_redirects=config.follow_redirects,
            max_redirects=config.max_redirects,
            headers={"User-Agent": user_agent},
        )

    try:
        for scheme in config.schemes:
            url = f"{scheme}://{domain}/"
            for attempt in range(max_attempts):
                request_method = config.method
                start = time.perf_counter()
                try:
                    response = await client.request(
                        request_method,
                        url,
                        follow_redirects=config.follow_redirects,
                        timeout=timeout_s,
                        headers={"User-Agent": user_agent},
                    )
                    if request_method == "HEAD" and response.status_code in {405, 501}:
                        response = await client.request(
                            "GET",
                            url,
                            follow_redirects=config.follow_redirects,
                            timeout=timeout_s,
                            headers={"User-Agent": user_agent},
                        )
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    return HTTPResult(
                        queried=True,
                        reachable=True,
                        scheme=scheme,
                        status_code=response.status_code,
                        final_url=str(response.url),
                        redirects=len(response.history),
                        latency_ms=latency_ms,
                        error=None,
                    )
                except asyncio.TimeoutError:
                    errors.append(f"{scheme} timeout (attempt {attempt + 1})")
                except httpx_lib.TimeoutException:
                    errors.append(f"{scheme} timeout (attempt {attempt + 1})")
                except httpx_lib.HTTPError as exc:
                    errors.append(f"{scheme} {exc.__class__.__name__}: {exc}")
    finally:
        if owns_client and client is not None:
            await client.aclose()

    return HTTPResult(
        queried=True,
        reachable=False,
        error="; ".join(errors) if errors else "No HTTP response",
    )
