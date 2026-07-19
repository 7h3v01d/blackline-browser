"""
adblock.py  —  pure filter-list logic, no Qt dependency.

Split out of interceptors.py so the matching rules can be tested directly
without spinning up QtWebEngine. AdBlockInterceptor is a thin Qt adapter
over FilterSet.

Design note — why so much is discarded:
EasyList rules carry context we do not have inside a
QWebEngineUrlRequestInterceptor (the initiating page, the resource type,
element-hiding selectors). Applying those rules globally is worse than
ignoring them: a rule scoped to one site silently breaks the whole web.
FilterSet therefore honours only unscoped domain anchors and matches on
host boundaries, never substrings.
"""

import logging
import re

logger = logging.getLogger(__name__)

# A bare hostname: labels of alphanumerics/hyphens/underscores, at least one dot.
_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-_.]*[a-z0-9])?$")

# Lines we never treat as domain rules.
_SKIP_PREFIXES = ("[", "!", "@@", "#", "/", "%", "&")


class FilterSet:
    """A set of blockable hostnames parsed from EasyList-style rules."""

    __slots__ = ("domains", "skipped")

    def __init__(self, domains=None, skipped: int = 0):
        self.domains = set(domains or ())
        self.skipped = skipped

    # ── parsing ──────────────────────────────────────────────────────────

    @staticmethod
    def parse_rule(line: str):
        """
        Extract a blockable hostname from one filter-list line, else None.

        Honoured:   ||doubleclick.net^
                    ||ads.example.com^$third-party
                    ||tracker.co.uk
        Rejected:   comments, element hiding (##), exceptions (@@),
                    regex rules, rules with a path, wildcards, and anything
                    carrying a $domain= scope (needs page context we lack).
        """
        if not line:
            return None
        line = line.strip()
        if not line or line.startswith(_SKIP_PREFIXES):
            return None
        if not line.startswith("||"):
            return None

        body = line[2:]
        options = ""
        if "$" in body:
            body, options = body.split("$", 1)

        # Element-hiding syntax can follow the domain on some lines.
        for sep in ("##", "#@#", "#?#"):
            if sep in body:
                return None

        body = body.split("^")[0].strip().lower()

        if not body:
            return None
        if "/" in body or "*" in body or "." not in body:
            return None
        if "domain=" in options.lower():
            return None
        if not _HOSTNAME_RE.match(body):
            return None
        if body.startswith(".") or body.endswith(".") or ".." in body:
            return None
        return body

    @classmethod
    def from_lines(cls, lines) -> "FilterSet":
        domains, skipped = set(), 0
        for line in lines:
            domain = cls.parse_rule(line)
            if domain:
                domains.add(domain)
            else:
                skipped += 1
        return cls(domains, skipped)

    @classmethod
    def from_file(cls, path: str, encoding: str = "utf-8") -> "FilterSet":
        with open(path, "r", encoding=encoding, errors="ignore") as fh:
            return cls.from_lines(fh)

    # ── matching ─────────────────────────────────────────────────────────

    def is_blocked(self, host: str) -> bool:
        """
        True if host matches a rule exactly or is a subdomain of one.

        Never a substring match. The substring form is what caused
        ||t.co^ (scoped to one site) to block reddi(t.co)m, github.com
        and www.youtube.com in earlier builds.
        """
        if not host:
            return False
        host = host.strip().lower().rstrip(".")
        if not host:
            return False
        if host in self.domains:
            return True
        parts = host.split(".")
        for i in range(1, len(parts) - 1):
            if ".".join(parts[i:]) in self.domains:
                return True
        return False

    def __len__(self) -> int:
        return len(self.domains)

    def __contains__(self, host: str) -> bool:
        return self.is_blocked(host)


def host_matches_any(host: str, suffixes) -> bool:
    """Exact-or-subdomain membership test, used for the whitelist."""
    if not host:
        return False
    host = host.strip().lower().rstrip(".")
    return any(host == s or host.endswith("." + s) for s in suffixes)
