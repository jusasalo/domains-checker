from __future__ import annotations

from typing import List


def ms_to_seconds(timeout_ms: int) -> float:
    return max(0.001, timeout_ms / 1000.0)


def compact_errors(errors: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for error in errors:
        item = error.strip()
        if not item or item in seen:
            continue
        output.append(item)
        seen.add(item)
    return output
