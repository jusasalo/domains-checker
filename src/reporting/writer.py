from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Sequence

from src.core.models import DomainResult, OutputConfig


def _public_status(status: str) -> str:
    if status == "registered":
        return "taken"
    if status == "available":
        return "available"
    return "unknown"


def _domain_without_tld(domain: str) -> str:
    if "." not in domain:
        return domain
    return domain.rsplit(".", 1)[0]


def _field_value(result: DomainResult, column: str) -> object:
    field_map = {
        "domain": _domain_without_tld(result.domain),
        "full_domain": result.domain,
        "tlds": result.tld,
        "status": _public_status(result.status),
        "expiration_date": result.registrar.expiration_date,
        "registrar_name": result.registrar.registrar_name,
        "registrar_url": result.registrar.registrar_url,
    }
    return field_map.get(column)


def _results_as_dicts(
    results: Sequence[DomainResult],
    columns: Sequence[str],
) -> List[Dict[str, object]]:
    payload: List[Dict[str, object]] = []
    for result in results:
        row: Dict[str, object] = {column: _field_value(result, column) for column in columns}
        row["dns"] = {
            "queried": result.dns.queried,
            "exists": result.dns.exists,
            "records": result.dns.records,
            "error": result.dns.error,
            "latency_ms": result.dns.latency_ms,
        }
        row["http"] = {
            "queried": result.http.queried,
            "reachable": result.http.reachable,
            "scheme": result.http.scheme,
            "status_code": result.http.status_code,
            "final_url": result.http.final_url,
            "redirects": result.http.redirects,
            "latency_ms": result.http.latency_ms,
            "error": result.http.error,
        }
        row["tls"] = {
            "queried": result.tls.queried,
            "handshake_ok": result.tls.handshake_ok,
            "issuer": result.tls.issuer,
            "subject_alt_names": result.tls.subject_alt_names,
            "not_before": result.tls.not_before,
            "not_after": result.tls.not_after,
            "days_to_expiry": result.tls.days_to_expiry,
            "expires_soon": result.tls.expires_soon,
            "tls_version": result.tls.tls_version,
            "cipher": result.tls.cipher,
            "error": result.tls.error,
            "skipped_reason": result.tls.skipped_reason,
        }
        row["errors"] = result.errors
        payload.append(row)
    return payload


def _write_json(
    path: Path,
    results: Sequence[DomainResult],
    columns: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(_results_as_dicts(results, columns), fh, indent=2, ensure_ascii=False)


def _write_csv(
    path: Path,
    results: Sequence[DomainResult],
    columns: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for result in results:
            row = {column: _field_value(result, column) for column in columns}
            writer.writerow({key: value if value is not None else "" for key, value in row.items()})


def write_outputs(
    results: Sequence[DomainResult],
    output_config: OutputConfig,
    output_dir: Path,
    out_json_override: Path | None = None,
) -> Dict[str, Path]:
    normalized = [fmt.strip().lower() for fmt in output_config.format]
    normalized = [fmt for fmt in normalized if fmt in {"json", "csv"}]
    if not normalized:
        normalized = ["json"]
    columns = list(output_config.columns)
    if not columns:
        columns = ["full_domain", "status", "expiration_date", "registrar_name", "registrar_url"]

    output_paths: Dict[str, Path] = {}
    base_dir = output_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    json_path = (base_dir / "results.json").resolve()
    csv_path = (base_dir / "results.csv").resolve()
    if out_json_override is not None:
        json_path = out_json_override.resolve()
        csv_path = json_path.with_suffix(".csv")

    if "json" in normalized:
        _write_json(json_path, results, columns)
        output_paths["json"] = json_path
    if "csv" in normalized:
        _write_csv(csv_path, results, columns)
        output_paths["csv"] = csv_path

    return output_paths
