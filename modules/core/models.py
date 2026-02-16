from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class DomainSource:
    domains: List[str]
    tlds: List[str]


@dataclass
class ConcurrencyConfig:
    max_tasks: int = 200
    per_host_limit: int = 10


@dataclass
class TimeoutsConfig:
    dns: int = 1500
    http: int = 3000
    tls: int = 3000


@dataclass
class RetriesConfig:
    dns: int = 1
    http: int = 1
    tls: int = 0
    registrar: int = 0


@dataclass
class DnsCheckConfig:
    enabled: bool = True
    record_types: List[str] = field(default_factory=lambda: ["A", "AAAA", "CNAME"])


@dataclass
class HttpCheckConfig:
    enabled: bool = True
    schemes: List[str] = field(default_factory=lambda: ["https", "http"])
    method: str = "HEAD"
    follow_redirects: bool = True
    max_redirects: int = 5


@dataclass
class TlsCheckConfig:
    enabled: bool = True
    only_if_https: bool = True
    check_expiry_days: int = 30


@dataclass
class RegistrarCheckConfig:
    enabled: bool = True


@dataclass
class ChecksConfig:
    dns: DnsCheckConfig = field(default_factory=DnsCheckConfig)
    http: HttpCheckConfig = field(default_factory=HttpCheckConfig)
    tls: TlsCheckConfig = field(default_factory=TlsCheckConfig)
    registrar: RegistrarCheckConfig = field(default_factory=RegistrarCheckConfig)


@dataclass
class VariantRules:
    leet: Dict[str, List[str]] = field(default_factory=dict)
    swap_adjacent: bool = True
    drop_char: bool = True
    duplicate_char: bool = False
    dash_insert: bool = True


@dataclass
class VariantsConfig:
    enabled: bool = True
    max_per_base: int = 40
    rules: VariantRules = field(default_factory=VariantRules)


@dataclass
class OutputConfig:
    format: List[str] = field(default_factory=lambda: ["json", "csv"])
    sort_by: List[str] = field(default_factory=lambda: ["domain"])
    console: bool = True
    columns: List[str] = field(
        default_factory=lambda: [
            "domain",
            "tlds",
            "status",
            "expiration_date",
            "registrar_name",
            "registrar_url",
        ]
    )
    console_domain_width: int = 20
    console_column_widths: Dict[str, int] = field(default_factory=dict)


@dataclass
class SearchConfig:
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    timeouts_ms: TimeoutsConfig = field(default_factory=TimeoutsConfig)
    retries: RetriesConfig = field(default_factory=RetriesConfig)
    checks: ChecksConfig = field(default_factory=ChecksConfig)
    variants: VariantsConfig = field(default_factory=VariantsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    user_agent: str = "DomainChecker/2.0"


@dataclass
class DomainCandidate:
    domain: str
    base: str
    variant: str
    tld: str
    strategies: Set[str] = field(default_factory=set)


@dataclass
class DNSResult:
    queried: bool = False
    exists: Optional[bool] = None
    records: Dict[str, List[str]] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: Optional[int] = None


@dataclass
class HTTPResult:
    queried: bool = False
    reachable: Optional[bool] = None
    scheme: Optional[str] = None
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    redirects: int = 0
    latency_ms: Optional[int] = None
    error: Optional[str] = None


@dataclass
class TLSResult:
    queried: bool = False
    handshake_ok: Optional[bool] = None
    issuer: Optional[str] = None
    subject_alt_names: List[str] = field(default_factory=list)
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    days_to_expiry: Optional[int] = None
    expires_soon: Optional[bool] = None
    tls_version: Optional[str] = None
    cipher: Optional[str] = None
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


@dataclass
class RegistrarResult:
    queried: bool = False
    is_registered: Optional[bool] = None
    expiration_date: Optional[str] = None
    registrar_name: Optional[str] = None
    registrar_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DomainResult:
    domain: str
    base: str
    variant: str
    tld: str
    strategies: List[str]
    status: str
    available: Optional[bool]
    active: bool
    resolves: bool
    dns: DNSResult = field(default_factory=DNSResult)
    http: HTTPResult = field(default_factory=HTTPResult)
    tls: TLSResult = field(default_factory=TLSResult)
    registrar: RegistrarResult = field(default_factory=RegistrarResult)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
