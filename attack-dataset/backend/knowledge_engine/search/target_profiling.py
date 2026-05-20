"""
Target profiling and attack-record relevance for attack-vector chaining.

Infers target class from hostname / detected services and filters or boosts
semantic-search candidates so web/e-commerce assessments do not surface
unrelated physical/RF/satellite techniques.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..core.models import AttackRecord, AttackResult

# Minimum combined relevance (0–1) to include a candidate in chains
MIN_RELEVANCE_SCORE = 0.32

# Social/scam lures unrelated to web pentest (unless explicit social-engineering scope)
SOCIAL_SCAM_EXCLUDE: Tuple[str, ...] = (
    "emoji vote",
    "vote scam",
    "vote fraud",
    "social media vote",
    "instagram vote",
    "facebook vote",
    "tiktok vote",
    "whatsapp vote",
    "telegram vote",
    "like farming",
    "follower scam",
    "giveaway scam",
    "crypto giveaway",
    "romance scam",
    "phishing lure unrelated",
    "smishing campaign",
    "vishing script",
)

WEB_BOOST_KEYWORDS: Tuple[str, ...] = (
    "web", "http", "https", "shopify", "e-commerce", "ecommerce", "owasp",
    "xss", "sqli", "sql injection", "injection", "csrf", "ssrf", "api",
    "rest", "graphql", "cdn", "waf", "cookie", "session", "oauth", "ssl",
    "tls", "cms", "wordpress", "drupal", "payment", "checkout", "cart",
    "application security", "browser", "html", "javascript", "cors",
    "authentication", "authorization", "directory traversal", "lfi", "rfi",
    "server-side", "client-side", "subdomain", "dns", "whois", "osint",
    "fingerprint", "nmap", "burp", "nikto", "dirb", "gobuster",
)

PHYSICAL_RF_IOT_EXCLUDE: Tuple[str, ...] = (
    "z-wave", "zwave", "satellite jam", "satellite spoof", "imsi catcher",
    "imsi-catcher", "gps jam", "gps spoof", "firefighting plane",
    "firefighting aircraft", "ar spoof", "augmented reality spoof",
    "zigbee", "lorawan", "cellular baseband", "software defined radio",
    "sdr attack", "ads-b", "aviation gps", "smart meter", "scada",
    "modbus", "plc attack", "mesh network iot", "bluetooth mesh",
    "nfc relay", "rfid cloning", "ham radio exploit", "motorola astro",
    "tetra ", "gsm interceptor", "stingray", "femtocell",
    "infotainment", "ota url injection", "firmware via public wi-fi",
    "iot web interface", "vehicle ", "automotive", "telematics",
    "cobalt strike",  # C2 / detection-rule entries, not baseline web recon
    "suricata rule",
    "wireless attack", "802.11", "wi-fi", "wifi ", "probe request harvesting",
    "bluetooth", "mesh network", "location faking in location-based",
)

ECOMMERCE_HOST_HINTS = re.compile(
    r"(shop|store|mart|buy|retail|commerce|citi|market|boutique|outlet)",
    re.I,
)


@dataclass
class TargetProfile:
    target_class: str = "generic"
    """web_application | network_host | ecommerce | generic"""
    host: str = ""
    search_hints: List[str] = field(default_factory=list)
    exclude_keywords: Tuple[str, ...] = field(default_factory=lambda: PHYSICAL_RF_IOT_EXCLUDE)
    boost_keywords: Tuple[str, ...] = field(default_factory=lambda: WEB_BOOST_KEYWORDS)


def _is_social_scam_title(text: str, *, allow_social_engineering: bool = False) -> bool:
    """Hard-exclude vote/emoji/scam chains for web/e-commerce assessments."""
    if allow_social_engineering:
        return False
    lower = text.lower()
    scam_tokens = ("vote", "emoji", "scam", "phishing lure", "like farming", "giveaway")
    if not any(tok in lower for tok in scam_tokens):
        return False
    return any(ex in lower for ex in SOCIAL_SCAM_EXCLUDE) or (
        "vote" in lower and ("emoji" in lower or "social media" in lower or "instagram" in lower)
    )


def _record_text(record: AttackRecord) -> str:
    return " ".join(
        filter(
            None,
            [
                record.title,
                record.category,
                record.attack_type,
                record.tags,
                record.mitre_technique,
                (record.scenario_description or "")[:400],
                record.target_type,
            ],
        )
    ).lower()


def _services_text(services: Sequence[str]) -> str:
    return " ".join(s.lower() for s in services)


def infer_target_profile(
    target_description: str,
    detected_services: Optional[Sequence[str]] = None,
) -> TargetProfile:
    """Infer target class and search hints from description + service labels."""
    desc = (target_description or "").lower()
    services = list(detected_services or [])
    svc_blob = _services_text(services)

    host_match = re.search(
        r"target[:\s]+([a-z0-9][a-z0-9.-]*\.[a-z]{2,})",
        desc,
        re.I,
    )
    host = host_match.group(1).lower() if host_match else ""
    if not host:
        domain_match = re.search(
            r"\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\.(?:[a-z]{2,}))\b",
            desc,
            re.I,
        )
        if domain_match:
            host = domain_match.group(1).lower()

    has_web_ports = any(
        p in svc_blob
        for p in ("port:443", "port:80", "port:8443", "port:8080", " https", " http")
    ) or any(
        s in svc_blob
        for s in ("https", "http", "ssl", "tls", "www", "nginx", "apache", "shopify")
    )
    has_web_in_desc = any(
        k in desc
        for k in (
            "web application",
            "e-commerce",
            "ecommerce",
            "shopify",
            "https",
            "http",
            "owasp",
            "online retail",
        )
    )
    is_domain = bool(host and "." in host and not re.match(r"^\d+\.\d+\.\d+\.\d+$", host))

    if has_web_ports or has_web_in_desc or (is_domain and not svc_blob.strip()):
        target_class = "ecommerce" if (host and ECOMMERCE_HOST_HINTS.search(host)) else "web_application"
        hints = [
            "web application security",
            "OWASP",
            "HTTP HTTPS",
            "public-facing application",
            "reconnaissance scanning",
        ]
        if target_class == "ecommerce":
            hints.extend(["e-commerce", "Shopify", "online store", "checkout", "payment API"])
        return TargetProfile(
            target_class=target_class,
            host=host,
            search_hints=hints,
            exclude_keywords=PHYSICAL_RF_IOT_EXCLUDE,
            boost_keywords=WEB_BOOST_KEYWORDS,
        )

  # SSH / database / network-heavy fingerprint
    if any(k in svc_blob for k in ("ssh", "port:22", "rdp", "port:3389", "smb", "port:445")):
        return TargetProfile(
            target_class="network_host",
            host=host,
            search_hints=["network penetration", "remote access", "credential access"],
            exclude_keywords=PHYSICAL_RF_IOT_EXCLUDE,
            boost_keywords=(
                "ssh", "rdp", "smb", "network", "lateral", "brute", "credential",
                "remote", "windows", "linux",
            ),
        )

    return TargetProfile(target_class="generic", host=host, search_hints=[])


def enrich_search_query(
    target_description: str,
    detected_services: Optional[Sequence[str]],
    detected_os: Optional[str],
    profile: TargetProfile,
) -> str:
    """Build a semantic-search query grounded in target class."""
    parts = [
        target_description,
        _services_text(detected_services or []),
        detected_os or "",
        " ".join(profile.search_hints),
    ]
    if profile.target_class in ("web_application", "ecommerce"):
        parts.append(
            "website security assessment penetration test not satellite not IoT radio"
        )
    return " ".join(p for p in parts if p).strip()


def keyword_relevance(record: AttackRecord, profile: TargetProfile) -> float:
    """Keyword-based relevance in [0, 1]; -1 means hard-exclude."""
    text = _record_text(record)

    for ex in profile.exclude_keywords:
        if ex in text:
            return -1.0

    if profile.target_class in ("web_application", "ecommerce"):
        if _is_social_scam_title(text):
            return -1.0
        cat = (record.category or "").lower()
        if any(
            x in cat
            for x in (
                "wireless",
                "satellite",
                "radio",
                "iot",
                "industrial",
                "vehicle",
                "aviation",
                "physical",
            )
        ):
            return -1.0
        hits = sum(1 for kw in profile.boost_keywords if kw in text)
        if hits == 0:
            # Penalize clearly non-web categories when profiling as web
            non_web = (
                "wireless sensor",
                "satellite",
                "radio frequency",
                "industrial control",
                "iot device",
                "iot ",
                "smart home",
                "vehicle",
                "aviation",
                "infotainment",
                "telematics",
                "firmware update",
                "suricata rule",
            )
            if any(nw in text for nw in non_web):
                return -1.0
            return 0.15
        return min(1.0, 0.25 + hits * 0.12)

    if profile.target_class == "network_host":
        hits = sum(1 for kw in profile.boost_keywords if kw in text)
        return min(1.0, 0.2 + hits * 0.15) if hits else 0.2

    return 0.5


def combined_relevance(
    semantic_score: float,
    record: AttackRecord,
    profile: TargetProfile,
) -> float:
    kw = keyword_relevance(record, profile)
    if kw < 0:
        return -1.0
    sem = max(0.0, min(1.0, semantic_score))
    if profile.target_class in ("web_application", "ecommerce"):
        return 0.55 * sem + 0.45 * kw
    return 0.7 * sem + 0.3 * kw


def filter_and_rerank_results(
    results: List[AttackResult],
    profile: TargetProfile,
    *,
    min_score: float = MIN_RELEVANCE_SCORE,
    max_candidates: int = 25,
) -> List[AttackResult]:
    """Drop irrelevant records and re-rank by target-aware relevance."""
    scored: List[Tuple[AttackResult, float]] = []
    for r in results:
        rel = combined_relevance(r.score, r.record, profile)
        if rel < min_score:
            continue
        scored.append((r, rel))

    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored and results:
        # Fallback: keep top semantic hits that are not hard-excluded
        for r in results[: max_candidates * 2]:
            if keyword_relevance(r.record, profile) >= 0:
                rel = max(r.score, min_score)
                scored.append((r, rel))
        scored.sort(key=lambda x: x[1], reverse=True)

    out: List[AttackResult] = []
    seen_titles: set = set()
    for r, rel in scored[:max_candidates]:
        title_key = (r.record.title or "").strip().lower()[:80]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        out.append(AttackResult(record=r.record, score=round(rel, 4)))
    return out
