from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from modules.checks.dns_check import run_dns_check
from modules.checks.http_check import run_http_check
from modules.checks.registrar_check import run_registrar_check
from modules.checks.tls_check import run_tls_check
from modules.core.models import (
    DNSResult,
    DomainCandidate,
    DomainResult,
    DomainSource,
    HTTPResult,
    RegistrarResult,
    SearchConfig,
    TLSResult,
)
from modules.core.tlds import expand_candidates
from modules.utils.concurrency import HostLimiter
from modules.utils.net import compact_errors, ms_to_seconds

try:
    import httpx as httpx_lib
except ImportError:  # pragma: no cover - optional dependency
    httpx_lib = None


def _host_key(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


def _determine_status(
    dns: DNSResult,
    http: HTTPResult,
    tls: TLSResult,
    registrar: RegistrarResult,
) -> Tuple[str, Optional[bool]]:
    if registrar.is_registered is True:
        return "registered", False
    if dns.exists is True or http.reachable is True or tls.handshake_ok is True:
        return "registered", False

    if registrar.is_registered is False:
        return "available", True

    nothing_reachable = (http.queried and http.reachable is False) or (not http.queried)
    tls_not_ok = (tls.queried and tls.handshake_ok is False) or (not tls.queried)
    if dns.queried and dns.exists is False and nothing_reachable and tls_not_ok:
        return "available", True

    return "unknown", None


def _merge_result(
    candidate: DomainCandidate,
    dns: DNSResult,
    http: HTTPResult,
    tls: TLSResult,
    registrar: RegistrarResult,
) -> DomainResult:
    errors = compact_errors(
        [
            error
            for error in [dns.error, http.error, tls.error, registrar.error]
            if isinstance(error, str)
        ]
    )
    status, available = _determine_status(dns, http, tls, registrar)
    return DomainResult(
        domain=candidate.domain,
        base=candidate.base,
        variant=candidate.variant,
        tld=candidate.tld,
        strategies=sorted(candidate.strategies),
        status=status,
        available=available,
        active=bool(http.reachable),
        resolves=bool(dns.exists),
        dns=dns,
        http=http,
        tls=tls,
        registrar=registrar,
        errors=errors,
    )


async def _process_candidate(
    candidate: DomainCandidate,
    config: SearchConfig,
    semaphore: asyncio.Semaphore,
    host_limiter: HostLimiter,
    http_client: Optional[object],
    registrar_tasks: dict[str, asyncio.Task[RegistrarResult]],
    registrar_lock: asyncio.Lock,
) -> DomainResult:
    async with semaphore:
        async with host_limiter.slot(_host_key(candidate.domain)):
            dns_result = DNSResult(queried=False)
            http_result = HTTPResult(queried=False)
            tls_result = TLSResult(queried=False)
            registrar_result = RegistrarResult(queried=False)

            if config.checks.dns.enabled:
                dns_result = await run_dns_check(
                    domain=candidate.domain,
                    config=config.checks.dns,
                    timeout_ms=config.timeouts_ms.dns,
                    retries=config.retries.dns,
                )
            if config.checks.http.enabled:
                http_result = await run_http_check(
                    domain=candidate.domain,
                    config=config.checks.http,
                    timeout_ms=config.timeouts_ms.http,
                    retries=config.retries.http,
                    user_agent=config.user_agent,
                    client=http_client,
                )

            should_run_tls = config.checks.tls.enabled
            if should_run_tls and config.checks.tls.only_if_https and config.checks.http.enabled:
                is_https = (
                    bool(http_result.reachable)
                    and (
                        (http_result.scheme == "https")
                        or (
                            isinstance(http_result.final_url, str)
                            and http_result.final_url.startswith("https://")
                        )
                    )
                )
                if not is_https:
                    should_run_tls = False
                    tls_result = TLSResult(
                        queried=False,
                        handshake_ok=None,
                        skipped_reason="Skipped because HTTPS is not reachable",
                    )

            if should_run_tls:
                tls_result = await run_tls_check(
                    domain=candidate.domain,
                    timeout_ms=config.timeouts_ms.tls,
                    retries=config.retries.tls,
                    check_expiry_days=config.checks.tls.check_expiry_days,
                )

            if config.checks.registrar.enabled:
                registrar_lookup_domain = f"{candidate.variant}.{candidate.tld}"
                async with registrar_lock:
                    lookup_task = registrar_tasks.get(registrar_lookup_domain)
                    if lookup_task is None:
                        lookup_task = asyncio.create_task(
                            run_registrar_check(
                                domain=registrar_lookup_domain,
                                timeout_ms=config.timeouts_ms.http,
                                retries=config.retries.registrar,
                                user_agent=config.user_agent,
                                client=http_client,
                            )
                        )
                        registrar_tasks[registrar_lookup_domain] = lookup_task
                try:
                    registrar_result = await lookup_task
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    registrar_result = RegistrarResult(
                        queried=True,
                        is_registered=None,
                        error=f"Registrar lookup failed: {exc}",
                    )

            return _merge_result(
                candidate,
                dns_result,
                http_result,
                tls_result,
                registrar_result,
            )


async def run_pipeline(
    source: DomainSource,
    config: SearchConfig,
) -> Tuple[List[DomainResult], List[str]]:
    candidates, warnings = expand_candidates(source, config.variants)
    if not candidates:
        return [], warnings

    semaphore = asyncio.Semaphore(max(1, config.concurrency.max_tasks))
    host_limiter = HostLimiter(config.concurrency.per_host_limit)
    registrar_tasks: dict[str, asyncio.Task[RegistrarResult]] = {}
    registrar_lock = asyncio.Lock()
    results: List[DomainResult] = []

    async def run_with_client(http_client: Optional[object]) -> None:
        tasks = [
            asyncio.create_task(
                _process_candidate(
                    candidate,
                    config,
                    semaphore,
                    host_limiter,
                    http_client,
                    registrar_tasks,
                    registrar_lock,
                )
            )
            for candidate in candidates
        ]
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
            except Exception as exc:  # pragma: no cover # pylint: disable=broad-exception-caught
                result = DomainResult(
                    domain="unknown",
                    base="unknown",
                    variant="unknown",
                    tld="unknown",
                    strategies=[],
                    status="unknown",
                    available=None,
                    active=False,
                    resolves=False,
                    registrar=RegistrarResult(queried=False),
                    errors=[f"Unhandled orchestrator error: {exc}"],
                )
            results.append(result)

    if config.checks.http.enabled and httpx_lib is not None:
        timeout_s = ms_to_seconds(config.timeouts_ms.http)
        limits = httpx_lib.Limits(
            max_connections=max(20, config.concurrency.max_tasks),
            max_keepalive_connections=max(10, min(100, config.concurrency.max_tasks)),
        )
        async with httpx_lib.AsyncClient(
            timeout=httpx_lib.Timeout(timeout_s),
            limits=limits,
            follow_redirects=config.checks.http.follow_redirects,
            max_redirects=config.checks.http.max_redirects,
            headers={"User-Agent": config.user_agent},
        ) as client:
            await run_with_client(client)
    else:
        await run_with_client(None)

    results.sort(key=lambda item: item.domain)
    return results, warnings
