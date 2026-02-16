from __future__ import annotations

import sys
from typing import Any, Iterable, List, Sequence

from modules.core.models import DomainResult, OutputConfig

try:
    from rich.console import Console as rich_console_class
except ImportError:  # pragma: no cover - optional dependency
    rich_console_class = None


def _resolve_path(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _sort_token(value: Any) -> Any:
    if value is None:
        return (3, "")
    if isinstance(value, bool):
        return (0, 0 if value else 1)
    if isinstance(value, (int, float)):
        return (1, value)
    return (2, str(value).lower())


def sort_results(results: Sequence[DomainResult], sort_by: Iterable[str]) -> List[DomainResult]:
    sort_keys = [key for key in sort_by if key]
    if not sort_keys:
        sort_keys = ["domain"]

    def key_builder(item: DomainResult) -> Any:
        payload = item.to_dict()
        return tuple(_sort_token(_resolve_path(payload, key)) for key in sort_keys)

    return sorted(results, key=key_builder)


def _status_color(status: str) -> str:
    return {
        "registered": "red",
        "available": "green",
        "unknown": "yellow",
    }.get(status, "white")


def _public_status(status: str) -> str:
    if status == "registered":
        return "taken"
    if status == "available":
        return "available"
    return "unknown"


def _ansi_color(text: str, status: str) -> str:
    if not sys.stdout.isatty():
        return text
    code = {
        "registered": "\033[91m",
        "available": "\033[92m",
        "unknown": "\033[93m",
    }.get(status, "")
    if not code:
        return text
    return f"{code}{text}\033[0m"


def _domain_without_tld(domain: str) -> str:
    if "." not in domain:
        return domain
    return domain.rsplit(".", 1)[0]


def _date_only(value: str) -> str:
    text = value.strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


def _field_text(result: DomainResult, column: str) -> str:
    field_map = {
        "domain": _domain_without_tld(result.domain),
        "full_domain": result.domain,
        "tlds": result.tld,
        "status": _public_status(result.status),
        "expiration_date": (
            _date_only(result.registrar.expiration_date)
            if result.registrar.expiration_date
            else "-"
        ),
        "registrar_name": result.registrar.registrar_name or "-",
        "registrar_url": result.registrar.registrar_url or "-",
    }
    return field_map.get(column, "-")


def _console_width(column: str, output_config: OutputConfig) -> int:
    custom_width = output_config.console_column_widths.get(column)
    if isinstance(custom_width, int) and custom_width > 0:
        return custom_width
    width_map = {
        "domain": max(8, output_config.console_domain_width),
        "full_domain": max(12, output_config.console_domain_width + 8),
        "tlds": 6,
        "status": 10,
        "expiration_date": 20,
        "registrar_name": 22,
        "registrar_url": 45,
    }
    return width_map.get(column, 0)


def _fit(value: str, width: int) -> str:
    if width <= 0:
        return value
    text = value.strip()
    if len(text) <= width:
        return f"{text:{width}}"
    if width <= 3:
        return text[:width]
    return f"{text[:width - 3]}..."


def render_console(results: Sequence[DomainResult], output_config: OutputConfig) -> None:
    columns = [column for column in output_config.columns if column != "registrar_url"]
    if not columns:
        columns = ["domain", "tlds", "status", "expiration_date", "registrar_name"]
    widths = {column: _console_width(column, output_config) for column in columns}
    header_parts = [_fit(column, widths[column]) for column in columns]
    header = " ".join(header_parts)

    if rich_console_class is not None:
        console = rich_console_class()
        console.print(header)
        for result in results:
            parts: List[str] = []
            for column in columns:
                text = _field_text(result, column)
                if column == "status":
                    color = _status_color(result.status)
                    parts.append(f"[{color}]{_fit(text, widths[column])}[/{color}]")
                else:
                    parts.append(_fit(text, widths[column]))
            console.print(" ".join(parts))
        return

    print(header)
    for result in results:
        parts = [
            _fit(_field_text(result, column), widths[column]) for column in columns
        ]
        line = " ".join(parts)
        print(_ansi_color(line, result.status))


def summarize_results(results: Sequence[DomainResult]) -> str:
    counters = {
        "registered": 0,
        "available": 0,
        "unknown": 0,
    }
    for result in results:
        if result.status in counters:
            counters[result.status] += 1
    return (
        f"Total={len(results)} | "
        f"taken={counters['registered']} | "
        f"available={counters['available']} | "
        f"unknown={counters['unknown']}"
    )
