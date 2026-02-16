from __future__ import annotations

import asyncio
import socket
import time
from typing import Dict, List

from modules.core.models import DNSResult, DnsCheckConfig
from modules.utils.net import ms_to_seconds

try:
    import dns.resolver as dns_resolver  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    dns_resolver = None


class _NXDomainError(Exception):
    pass


def _resolve_with_dnspython(domain: str, record_type: str, timeout_s: float) -> List[str]:
    resolver = dns_resolver.Resolver()  # type: ignore[union-attr]
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s
    try:
        answer = resolver.resolve(domain, record_type, raise_on_no_answer=False)
    except dns_resolver.NXDOMAIN as exc:  # type: ignore[union-attr]
        raise _NXDomainError(str(exc)) from exc
    except dns_resolver.NoAnswer:  # type: ignore[union-attr]
        return []
    except dns_resolver.NoNameservers:  # type: ignore[union-attr]
        return []

    values: List[str] = []
    for item in answer:
        value = item.to_text().strip().rstrip(".")
        if value:
            values.append(value)
    return sorted(set(values))


def _resolve_with_socket(domain: str, record_type: str) -> List[str]:
    family = {
        "A": socket.AF_INET,
        "AAAA": socket.AF_INET6,
    }.get(record_type)
    if family is None:
        return []
    try:
        addrinfo = socket.getaddrinfo(domain, None, family, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        if exc.errno in {socket.EAI_NONAME, getattr(socket, "EAI_NODATA", socket.EAI_NONAME)}:
            raise _NXDomainError(str(exc)) from exc
        raise

    values = sorted({entry[4][0] for entry in addrinfo if entry and entry[4]})
    return values


def _resolve_record_sync(domain: str, record_type: str, timeout_s: float) -> List[str]:
    if dns_resolver is not None:
        return _resolve_with_dnspython(domain, record_type, timeout_s)
    return _resolve_with_socket(domain, record_type)


async def _resolve_record(domain: str, record_type: str, timeout_s: float) -> List[str]:
    return await asyncio.wait_for(
        asyncio.to_thread(_resolve_record_sync, domain, record_type, timeout_s),
        timeout=timeout_s + 0.2,
    )


async def run_dns_check(
    domain: str,
    config: DnsCheckConfig,
    timeout_ms: int,
    retries: int,
) -> DNSResult:
    timeout_s = ms_to_seconds(timeout_ms)
    max_attempts = max(1, retries + 1)
    unsupported_types = [
        record_type
        for record_type in config.record_types
        if record_type == "CNAME" and dns_resolver is None
    ]

    for attempt in range(max_attempts):
        start = time.perf_counter()
        records: Dict[str, List[str]] = {}
        errors: List[str] = []
        saw_nxdomain = False

        for record_type in config.record_types:
            try:
                values = await _resolve_record(domain, record_type, timeout_s)
                if values:
                    records[record_type] = values
            except _NXDomainError:
                saw_nxdomain = True
                break
            except asyncio.TimeoutError:
                errors.append(f"{record_type} timeout")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(f"{record_type} error: {exc}")

        latency_ms = int((time.perf_counter() - start) * 1000)
        if records:
            return DNSResult(
                queried=True,
                exists=True,
                records=records,
                error=None,
                latency_ms=latency_ms,
            )
        if saw_nxdomain:
            return DNSResult(
                queried=True,
                exists=False,
                records={},
                error="NXDOMAIN",
                latency_ms=latency_ms,
            )
        if attempt < max_attempts - 1:
            continue

        if unsupported_types:
            errors.append("CNAME requires dnspython package")
        error_text = "; ".join(errors) if errors else None
        return DNSResult(
            queried=True,
            exists=False,
            records={},
            error=error_text,
            latency_ms=latency_ms,
        )

    return DNSResult(queried=True, exists=False, records={}, error="DNS unknown error")
