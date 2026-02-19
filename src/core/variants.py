from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set

from src.core.models import VariantsConfig


LABEL_RE = re.compile(r"^[a-z0-9-]{1,63}$")


def _is_valid_label(label: str) -> bool:
    if not LABEL_RE.fullmatch(label):
        return False
    if label.startswith("-") or label.endswith("-"):
        return False
    return True


def _generate_leet(base: str, leet_map: Dict[str, List[str]], limit: int) -> List[str]:
    if not leet_map or limit <= 0:
        return []
    variants: List[str] = [base]
    seen = {base}
    for idx, char in enumerate(base):
        replacements = leet_map.get(char, [])
        if not replacements:
            continue
        snapshot = list(variants)
        for existing in snapshot:
            for replacement in replacements:
                candidate = f"{existing[:idx]}{replacement}{existing[idx + 1:]}"
                if candidate == base or candidate in seen:
                    continue
                if not _is_valid_label(candidate):
                    continue
                seen.add(candidate)
                variants.append(candidate)
                if len(variants) - 1 >= limit:
                    return variants[1:]
    return variants[1:]


def _generate_swap_adjacent(base: str, limit: int) -> List[str]:
    variants: List[str] = []
    seen = set()
    for idx in range(len(base) - 1):
        if base[idx] == base[idx + 1]:
            continue
        chars = list(base)
        chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        candidate = "".join(chars)
        if candidate in seen or not _is_valid_label(candidate):
            continue
        variants.append(candidate)
        seen.add(candidate)
        if len(variants) >= limit:
            break
    return variants


def _generate_drop_char(base: str, limit: int) -> List[str]:
    if len(base) <= 1:
        return []
    variants: List[str] = []
    seen = set()
    for idx in range(len(base)):
        candidate = f"{base[:idx]}{base[idx + 1:]}"
        if candidate in seen or not _is_valid_label(candidate):
            continue
        variants.append(candidate)
        seen.add(candidate)
        if len(variants) >= limit:
            break
    return variants


def _generate_duplicate_char(base: str, limit: int) -> List[str]:
    variants: List[str] = []
    seen = set()
    for idx, char in enumerate(base):
        if not char.isalnum():
            continue
        candidate = f"{base[:idx + 1]}{char}{base[idx + 1:]}"
        if candidate in seen or not _is_valid_label(candidate):
            continue
        variants.append(candidate)
        seen.add(candidate)
        if len(variants) >= limit:
            break
    return variants


def _generate_dash_insert(base: str, limit: int) -> List[str]:
    variants: List[str] = []
    seen = set()
    for idx in range(1, len(base)):
        if base[idx - 1] == "-" or base[idx] == "-":
            continue
        candidate = f"{base[:idx]}-{base[idx:]}"
        if candidate in seen or not _is_valid_label(candidate):
            continue
        variants.append(candidate)
        seen.add(candidate)
        if len(variants) >= limit:
            break
    return variants


def _add_candidates(
    target: Dict[str, Set[str]],
    candidates: Iterable[str],
    strategy: str,
    limit: int,
) -> int:
    created = 0
    for candidate in candidates:
        if candidate in target:
            target[candidate].add(strategy)
            continue
        if created >= limit:
            return created
        target[candidate] = {strategy}
        created += 1
    return created


def generate_variant_map(base: str, variants_cfg: VariantsConfig) -> Dict[str, Set[str]]:
    variant_map: Dict[str, Set[str]] = {base: set()}
    if not variants_cfg.enabled:
        return variant_map

    remaining = max(0, int(variants_cfg.max_per_base))
    rules = variants_cfg.rules

    if remaining > 0 and rules.leet:
        remaining -= _add_candidates(
            variant_map,
            _generate_leet(base, rules.leet, remaining),
            "leet",
            remaining,
        )
    if remaining > 0 and rules.swap_adjacent:
        remaining -= _add_candidates(
            variant_map,
            _generate_swap_adjacent(base, remaining),
            "swap_adjacent",
            remaining,
        )
    if remaining > 0 and rules.drop_char:
        remaining -= _add_candidates(
            variant_map,
            _generate_drop_char(base, remaining),
            "drop_char",
            remaining,
        )
    if remaining > 0 and rules.duplicate_char:
        remaining -= _add_candidates(
            variant_map,
            _generate_duplicate_char(base, remaining),
            "duplicate_char",
            remaining,
        )
    if remaining > 0 and rules.dash_insert:
        _add_candidates(
            variant_map,
            _generate_dash_insert(base, remaining),
            "dash_insert",
            remaining,
        )

    return variant_map
