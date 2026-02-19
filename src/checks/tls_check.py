from __future__ import annotations

import asyncio
import math
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.models import TLSResult
from src.utils.net import ms_to_seconds


def _flatten_name(entries: Any) -> Optional[str]:
    if not isinstance(entries, (list, tuple)):
        return None
    parts: List[str] = []
    for entry in entries:
        if not isinstance(entry, (list, tuple)):
            continue
        for item in entry:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            key = str(item[0]).strip()
            value = str(item[1]).strip()
            if key and value:
                parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else None


def _parse_cert_time(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        parsed = datetime.strptime(raw_value, "%b %d %H:%M:%S %Y %Z")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _probe_tls_sync(domain: str, timeout_s: float) -> Dict[str, Any]:
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=timeout_s) as tcp_sock:
        with context.wrap_socket(tcp_sock, server_hostname=domain) as tls_sock:
            cert = tls_sock.getpeercert()
            issuer = _flatten_name(cert.get("issuer"))
            san_entries = cert.get("subjectAltName", [])
            san: List[str] = []
            for san_entry in san_entries:
                if isinstance(san_entry, tuple) and len(san_entry) == 2 and san_entry[0] == "DNS":
                    san.append(str(san_entry[1]))

            not_before_raw = cert.get("notBefore")
            not_after_raw = cert.get("notAfter")
            not_before_dt = _parse_cert_time(not_before_raw)
            not_after_dt = _parse_cert_time(not_after_raw)

            days_to_expiry = None
            if not_after_dt is not None:
                remaining = (not_after_dt - datetime.now(timezone.utc)).total_seconds() / 86400
                days_to_expiry = int(math.floor(remaining))

            cipher_info = tls_sock.cipher()
            cipher = cipher_info[0] if cipher_info else None

            return {
                "issuer": issuer,
                "subject_alt_names": sorted(set(san)),
                "not_before": not_before_dt.isoformat() if not_before_dt else not_before_raw,
                "not_after": not_after_dt.isoformat() if not_after_dt else not_after_raw,
                "days_to_expiry": days_to_expiry,
                "tls_version": tls_sock.version(),
                "cipher": cipher,
            }


async def run_tls_check(
    domain: str,
    timeout_ms: int,
    retries: int,
    check_expiry_days: int,
) -> TLSResult:
    timeout_s = ms_to_seconds(timeout_ms)
    max_attempts = max(1, retries + 1)
    last_error: Optional[str] = None

    for _attempt in range(max_attempts):
        try:
            payload = await asyncio.wait_for(
                asyncio.to_thread(_probe_tls_sync, domain, timeout_s),
                timeout=timeout_s + 0.2,
            )
            days_to_expiry = payload.get("days_to_expiry")
            expires_soon = (
                bool(days_to_expiry <= check_expiry_days)
                if isinstance(days_to_expiry, int)
                else None
            )
            return TLSResult(
                queried=True,
                handshake_ok=True,
                issuer=payload.get("issuer"),
                subject_alt_names=payload.get("subject_alt_names", []),
                not_before=payload.get("not_before"),
                not_after=payload.get("not_after"),
                days_to_expiry=days_to_expiry,
                expires_soon=expires_soon,
                tls_version=payload.get("tls_version"),
                cipher=payload.get("cipher"),
                error=None,
            )
        except asyncio.TimeoutError:
            last_error = "TLS timeout"
        except ssl.SSLError as exc:
            last_error = f"TLS SSL error: {exc}"
        except OSError as exc:
            last_error = f"TLS OS error: {exc}"
        except Exception as exc:  # pragma: no cover # pylint: disable=broad-exception-caught
            last_error = f"TLS error: {exc}"

    return TLSResult(
        queried=True,
        handshake_ok=False,
        error=last_error or "TLS handshake failed",
    )
