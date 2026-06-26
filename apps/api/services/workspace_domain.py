import re

_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def normalize_domain(domain: str) -> str:
    d = domain.lower().strip()
    if d.startswith("@"):
        d = d[1:]
    return d


def is_valid_domain(domain: str) -> bool:
    norm = normalize_domain(domain)
    return bool(norm and _DOMAIN_RE.match(norm))


def email_matches_domain(email: str, domain: str) -> bool:
    norm = normalize_domain(domain)
    if not norm:
        return False
    parts = email.lower().strip().split("@")
    return len(parts) == 2 and parts[1] == norm


def extract_email_domain(email: str) -> str:
    return email.lower().strip().split("@")[-1]
