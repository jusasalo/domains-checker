from __future__ import annotations

from typing import Any, List, Optional, Tuple

from src.core.models import RegistrarResult
from src.utils.net import ms_to_seconds

try:
    import httpx as httpx_lib
except ImportError:  # pragma: no cover - optional dependency
    httpx_lib = None


RDAP_LOOKUP_URL = "https://rdap.org/domain/{domain}"


def _normalize_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split())
    return compact or None


def _first_http_url(value: Any) -> Optional[str]:
    normalized = _normalize_text(value)
    if normalized and normalized.startswith(("http://", "https://")):
        return normalized
    return None


def _vcard_value(entity: dict[str, Any], key: str) -> Optional[str]:
    vcard = entity.get("vcardArray")
    if not (isinstance(vcard, list) and len(vcard) == 2 and isinstance(vcard[1], list)):
        return None
    for item in vcard[1]:
        if not (isinstance(item, list) and len(item) >= 4):
            continue
        prop_name = str(item[0]).strip().lower()
        if prop_name != key:
            continue
        normalized = _normalize_text(item[3])
        if normalized:
            return normalized
    return None


def _link_url(entity: dict[str, Any]) -> Optional[str]:
    links = entity.get("links")
    if not isinstance(links, list):
        return None
    for item in links:
        if not isinstance(item, dict):
            continue
        href = _first_http_url(item.get("href"))
        if href:
            return href
    return None


def _extract_from_entity(entity: dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    name = _vcard_value(entity, "fn")
    if not name:
        handle = entity.get("handle")
        name = _normalize_text(handle)

    url = _vcard_value(entity, "url")
    if not url:
        url = _link_url(entity)

    return name, url


def _extract_registrar(payload: dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    entities = payload.get("entities")
    if isinstance(entities, list):
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            roles = entity.get("roles")
            normalized_roles = []
            if isinstance(roles, list):
                normalized_roles = [str(role).strip().lower() for role in roles]
            if "registrar" in normalized_roles:
                name, url = _extract_from_entity(entity)
                return name, url

    registrar = payload.get("registrar")
    if isinstance(registrar, dict):
        name = (
            _normalize_text(registrar.get("name"))
            if isinstance(registrar.get("name"), str)
            else None
        )
        url = _first_http_url(registrar.get("url"))
        return name, url
    normalized_registrar = _normalize_text(registrar)
    if normalized_registrar:
        return normalized_registrar, None

    registrar_name = payload.get("registrarName")
    normalized_name = _normalize_text(registrar_name)
    if normalized_name:
        return normalized_name, None
    return None, None


def _extract_expiration_date(payload: dict[str, Any]) -> Optional[str]:
    events = payload.get("events")
    if isinstance(events, list):
        for item in events:
            if not isinstance(item, dict):
                continue
            action = _normalize_text(item.get("eventAction"))
            event_date = _normalize_text(item.get("eventDate"))
            if not action or not event_date:
                continue
            if "expir" in action.lower():
                return event_date

    for key in ("expirationDate", "expiresDate", "registryExpiryDate"):
        value = _normalize_text(payload.get(key))
        if value:
            return value
    return None


async def run_registrar_check(
    domain: str,
    timeout_ms: int,
    retries: int,
    user_agent: str,
    client: Optional[Any] = None,
) -> RegistrarResult:
    if httpx_lib is None:
        return RegistrarResult(
            queried=True,
            is_registered=None,
            error="httpx not installed. Run: pip install httpx",
        )

    timeout_s = ms_to_seconds(timeout_ms)
    max_attempts = max(1, retries + 1)
    errors: List[str] = []

    owns_client = client is None
    if owns_client:
        client = httpx_lib.AsyncClient(
            timeout=httpx_lib.Timeout(timeout_s),
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    try:
        lookup_url = RDAP_LOOKUP_URL.format(domain=domain)
        for attempt in range(max_attempts):
            try:
                response = await client.get(lookup_url, timeout=timeout_s)
                if response.status_code == 404:
                    return RegistrarResult(queried=True, is_registered=False)
                if response.status_code == 200:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        return RegistrarResult(
                            queried=True,
                            is_registered=None,
                            error="Invalid RDAP payload",
                        )
                    registrar_name, registrar_url = _extract_registrar(payload)
                    expiration_date = _extract_expiration_date(payload)
                    return RegistrarResult(
                        queried=True,
                        is_registered=True,
                        expiration_date=expiration_date,
                        registrar_name=registrar_name,
                        registrar_url=registrar_url,
                    )
                if response.status_code in {429, 500, 502, 503, 504}:
                    errors.append(
                        f"RDAP HTTP {response.status_code} (attempt {attempt + 1})"
                    )
                    continue
                text = response.text.lower()
                if "not found" in text or "no object found" in text:
                    return RegistrarResult(queried=True, is_registered=False)
                errors.append(f"RDAP HTTP {response.status_code}")
            except httpx_lib.TimeoutException:
                errors.append(f"RDAP timeout (attempt {attempt + 1})")
            except httpx_lib.HTTPError as exc:
                errors.append(f"RDAP {exc.__class__.__name__}: {exc}")
            except ValueError as exc:
                errors.append(f"RDAP parse error: {exc}")
    finally:
        if owns_client and client is not None:
            await client.aclose()

    return RegistrarResult(
        queried=True,
        is_registered=None,
        error="; ".join(errors) if errors else "RDAP lookup failed",
    )
