from __future__ import annotations

from typing import Dict, List, Tuple

from modules.core.models import DomainCandidate, DomainSource, VariantsConfig
from modules.core.variants import generate_variant_map


def expand_candidates(
    source: DomainSource,
    variants_cfg: VariantsConfig,
) -> Tuple[List[DomainCandidate], List[str]]:
    warnings: List[str] = []
    candidate_map: Dict[str, DomainCandidate] = {}

    for base in source.domains:
        variant_map = generate_variant_map(base, variants_cfg)
        for variant, strategy_set in variant_map.items():
            for tld in source.tlds:
                fqdn = f"{variant}.{tld}"
                existing = candidate_map.get(fqdn)
                if existing is None:
                    candidate_map[fqdn] = DomainCandidate(
                        domain=fqdn,
                        base=base,
                        variant=variant,
                        tld=tld,
                        strategies=set(strategy_set),
                    )
                else:
                    existing.strategies.update(strategy_set)

    candidates = list(candidate_map.values())
    candidates.sort(key=lambda item: item.domain)
    if not candidates:
        warnings.append("No se generaron candidatos.")
    return candidates, warnings
