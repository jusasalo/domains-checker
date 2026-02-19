from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import (
    ChecksConfig,
    ConcurrencyConfig,
    DnsCheckConfig,
    DomainSource,
    HttpCheckConfig,
    OutputConfig,
    RegistrarCheckConfig,
    RetriesConfig,
    SearchConfig,
    TimeoutsConfig,
    TlsCheckConfig,
    VariantRules,
    VariantsConfig,
)


LABEL_RE = re.compile(r"^[a-z0-9-]{1,63}$")
TLD_RE = re.compile(r"^[a-z0-9-]{2,63}$")

DEFAULT_DOMAINS_FILE = Path("domains.json")
DEFAULT_CONFIG_FILE = Path("config.json")
DEFAULT_OUTPUT_DIR = Path("output")

DEFAULT_CONFIG: Dict[str, Any] = {
    "variation": {
        "variation_check": False,
        "variation_list": {
            "a": ["4"],
            "e": ["3", "6"],
            "i": ["1"],
            "o": ["0"],
            "b": ["8"],
            "c": ["6"],
            "g": ["6", "9"],
            "l": ["1"],
            "m": ["3"],
            "q": ["9"],
            "s": ["5"],
            "t": ["7"],
            "z": ["2"],
        },
    },
    "timeout_seconds": 5,
    "check_ssl": True,
    "check_dns": True,
    "check_registrar": True,
    "take_screenshot": False,
    "max_variants_per_domain": 40,
    "concurrency": {
        "max_tasks": 200,
        "per_host_limit": 10,
    },
    "retries": {
        "dns": 1,
        "http": 1,
        "tls": 0,
        "registrar": 1,
    },
    "output": {
        "dir": "output",
        "format": ["json", "csv"],
        "console": True,
        "sort_by": [],
        "columns": [
            "full_domain",
            "status",
            "expiration_date",
            "registrar_name",
            "registrar_url",
        ],
        "console_domain_width": 20,
        "console_column_widths": {
            "full_domain": 24,
            "status": 10,
            "expiration_date": 20,
            "registrar_name": 22,
            "registrar_url": 45,
        },
    },
    "user_agent": "DomainChecker/2.0",
}


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo: {path}")
    with path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON invalido en {path}: debe ser objeto")
    return payload


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_label(value: str) -> str:
    return value.strip().lower()


def _normalize_tld(value: str) -> str:
    return value.strip().lower().lstrip(".")


def _is_valid_label(label: str) -> bool:
    if not LABEL_RE.fullmatch(label):
        return False
    if label.startswith("-") or label.endswith("-"):
        return False
    return True


def _is_valid_tld(tld: str) -> bool:
    if not TLD_RE.fullmatch(tld):
        return False
    if tld.startswith("-") or tld.endswith("-"):
        return False
    return True


def _as_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _dedupe_keep_order(values: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped


def _resolve_path(base_dir: Path, maybe_relative: str | Path) -> Path:
    path = Path(maybe_relative)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _normalize_variations(raw_variations: Any, warnings: List[str]) -> Dict[str, List[str]]:
    if not isinstance(raw_variations, dict):
        return {}
    variations: Dict[str, List[str]] = {}
    for key, value in raw_variations.items():
        source = _normalize_label(str(key))
        if len(source) != 1 or not source.isalnum():
            warnings.append(f"Variacion invalida ignorada (clave): {key}")
            continue
        if not isinstance(value, list):
            warnings.append(f"Variacion invalida ignorada (valor): {key}")
            continue
        replacements: List[str] = []
        for item in value:
            target = _normalize_label(str(item))
            if len(target) != 1 or not target.isalnum():
                warnings.append(f"Variacion invalida ignorada en {key}: {item}")
                continue
            replacements.append(target)
        replacements = _dedupe_keep_order(replacements)
        if replacements:
            variations[source] = replacements
    return variations


def _normalize_output_formats(raw_formats: Any) -> List[str]:
    if isinstance(raw_formats, str):
        raw_items = [raw_formats]
    elif isinstance(raw_formats, list):
        raw_items = raw_formats
    else:
        raw_items = ["json"]

    formats: List[str] = []
    for item in raw_items:
        text = str(item).strip().lower()
        if text in {"json", "csv"}:
            formats.append(text)
    return _dedupe_keep_order(formats) or ["json"]


def _normalize_sort_by(raw_sort_by: Any) -> List[str]:
    if not isinstance(raw_sort_by, list):
        return []
    sort_by = [str(item).strip() for item in raw_sort_by]
    sort_by = [item for item in sort_by if item]
    return _dedupe_keep_order(sort_by)


def _normalize_output_columns(raw_columns: Any) -> List[str]:
    allowed = {
        "domain",
        "full_domain",
        "tlds",
        "status",
        "expiration_date",
        "registrar_name",
        "registrar_url",
    }
    if not isinstance(raw_columns, list):
        return [
            "full_domain",
            "status",
            "expiration_date",
            "registrar_name",
            "registrar_url",
        ]
    columns = [str(item).strip() for item in raw_columns]
    columns = [item for item in columns if item in allowed]
    columns = _dedupe_keep_order(columns)
    if "full_domain" not in columns and (
        "domain" in columns or "tlds" in columns
    ):
        merged_columns: List[str] = []
        inserted = False
        for column in columns:
            if column in {"domain", "tlds"}:
                if not inserted:
                    merged_columns.append("full_domain")
                    inserted = True
                continue
            merged_columns.append(column)
        columns = _dedupe_keep_order(merged_columns)
    return columns or [
        "full_domain",
        "status",
        "expiration_date",
        "registrar_name",
        "registrar_url",
    ]


def _normalize_column_widths(raw_widths: Any) -> Dict[str, int]:
    if not isinstance(raw_widths, dict):
        return {}
    widths: Dict[str, int] = {}
    for key, value in raw_widths.items():
        column = str(key).strip()
        width = _as_positive_int(value, 0)
        if column and width > 0:
            widths[column] = width
    return widths


def load_domains_file(path: Path) -> Tuple[List[str], List[str], List[str]]:
    payload = _read_json(path)
    warnings: List[str] = []
    raw_domains = payload.get("domains")
    if not isinstance(raw_domains, list) or not raw_domains:
        raise ValueError(f"{path}: 'domains' debe ser lista no vacia")

    domains: List[str] = []
    for item in raw_domains:
        label = _normalize_label(str(item))
        if not _is_valid_label(label):
            warnings.append(f"Domain label invalido ignorado: {item}")
            continue
        domains.append(label)
    domains = _dedupe_keep_order(domains)
    if not domains:
        raise ValueError(f"{path}: no quedaron dominios validos")
    raw_tlds = payload.get("tlds")
    if not isinstance(raw_tlds, list) or not raw_tlds:
        raise ValueError(f"{path}: 'tlds' debe ser lista no vacia")

    tlds: List[str] = []
    for item in raw_tlds:
        tld = _normalize_tld(str(item))
        if not _is_valid_tld(tld):
            warnings.append(f"TLD invalido ignorado: {item}")
            continue
        tlds.append(tld)
    tlds = _dedupe_keep_order(tlds)
    if not tlds:
        raise ValueError(f"{path}: no quedaron TLDs validos")
    return domains, tlds, warnings


def load_config_file(path: Path) -> Tuple[SearchConfig, Path, List[str]]:
    user_payload = _read_json(path)
    merged = _deep_merge(DEFAULT_CONFIG, user_payload)
    warnings: List[str] = []

    timeout_seconds = _as_positive_int(merged.get("timeout_seconds"), 5)
    timeout_ms = timeout_seconds * 1000
    check_ssl = bool(merged.get("check_ssl", True))
    check_dns = bool(merged.get("check_dns", True))
    check_registrar = bool(merged.get("check_registrar", True))
    take_screenshot = bool(merged.get("take_screenshot", False))
    if take_screenshot:
        warnings.append("take_screenshot=true no esta implementado y sera ignorado")

    variation_payload = merged.get("variation")
    if isinstance(variation_payload, dict):
        has_new_variation = (
            "variation_check" in variation_payload
            or "variation_list" in variation_payload
        )
        if has_new_variation:
            variation_check = bool(variation_payload.get("variation_check", False))
            raw_variations = variation_payload.get("variation_list", {})
        else:
            variation_check = bool(variation_payload.get("check_variations", False))
            raw_variations = variation_payload.get("variations_list", {})
            if not raw_variations:
                raw_variations = variation_payload
    else:
        legacy_variations_payload = merged.get("variations", {})
        if isinstance(legacy_variations_payload, dict):
            has_legacy_nested = (
                "check_variations" in legacy_variations_payload
                or "variations_list" in legacy_variations_payload
            )
            if has_legacy_nested:
                variation_check = bool(legacy_variations_payload.get("check_variations", False))
                raw_variations = legacy_variations_payload.get("variations_list", {})
            else:
                variation_check = bool(merged.get("check_variations", False))
                raw_variations = legacy_variations_payload
        else:
            variation_check = bool(merged.get("check_variations", False))
            raw_variations = legacy_variations_payload

    variations = _normalize_variations(raw_variations, warnings)
    max_variants = _as_positive_int(merged.get("max_variants_per_domain"), 40)

    concurrency = ConcurrencyConfig(
        max_tasks=_as_positive_int(merged.get("concurrency", {}).get("max_tasks"), 200),
        per_host_limit=_as_positive_int(merged.get("concurrency", {}).get("per_host_limit"), 10),
    )
    retries = RetriesConfig(
        dns=_as_non_negative_int(merged.get("retries", {}).get("dns"), 1),
        http=_as_non_negative_int(merged.get("retries", {}).get("http"), 1),
        tls=_as_non_negative_int(merged.get("retries", {}).get("tls"), 0),
        registrar=_as_non_negative_int(merged.get("retries", {}).get("registrar"), 0),
    )

    output_payload = merged.get("output", {})
    output_formats = _normalize_output_formats(output_payload.get("format"))
    output_sort_by = _normalize_sort_by(output_payload.get("sort_by"))
    output_columns = _normalize_output_columns(output_payload.get("columns"))
    console_domain_width = _as_positive_int(
        output_payload.get("console_domain_width"),
        20,
    )
    console_column_widths = _normalize_column_widths(
        output_payload.get("console_column_widths")
    )
    output_dir = _resolve_path(
        path.resolve().parent,
        output_payload.get("dir", str(DEFAULT_OUTPUT_DIR)),
    )

    checks = ChecksConfig(
        dns=DnsCheckConfig(enabled=check_dns, record_types=["A", "AAAA", "CNAME"]),
        http=HttpCheckConfig(
            enabled=True,
            schemes=["https", "http"] if check_ssl else ["http"],
            method="HEAD",
            follow_redirects=True,
            max_redirects=5,
        ),
        tls=TlsCheckConfig(
            enabled=check_ssl,
            only_if_https=True,
            check_expiry_days=_as_non_negative_int(merged.get("ssl_expiry_days"), 30),
        ),
        registrar=RegistrarCheckConfig(enabled=check_registrar),
    )

    search_config = SearchConfig(
        concurrency=concurrency,
        timeouts_ms=TimeoutsConfig(dns=timeout_ms, http=timeout_ms, tls=timeout_ms),
        retries=retries,
        checks=checks,
        variants=VariantsConfig(
            enabled=variation_check and bool(variations),
            max_per_base=max_variants,
            rules=VariantRules(
                leet=variations,
                swap_adjacent=False,
                drop_char=False,
                duplicate_char=False,
                dash_insert=False,
            ),
        ),
        output=OutputConfig(
            format=output_formats,
            sort_by=output_sort_by,
            console=bool(output_payload.get("console", True)),
            columns=output_columns,
            console_domain_width=console_domain_width,
            console_column_widths=console_column_widths,
        ),
        user_agent=(
            str(merged.get("user_agent", "DomainChecker/2.0")).strip()
            or "DomainChecker/2.0"
        ),
    )
    return search_config, output_dir, warnings


def load_bundle(
    domains_file: Optional[Path],
    config_file: Optional[Path],
) -> Tuple[DomainSource, SearchConfig, Path, List[str]]:
    cwd = Path.cwd()
    domains_path = _resolve_path(cwd, domains_file or DEFAULT_DOMAINS_FILE)
    config_path = _resolve_path(cwd, config_file or DEFAULT_CONFIG_FILE)

    domains, tlds, domain_warnings = load_domains_file(domains_path)
    config, output_dir, config_warnings = load_config_file(config_path)
    source = DomainSource(domains=domains, tlds=tlds)
    warnings = domain_warnings + config_warnings
    return source, config, output_dir, warnings
