#!/usr/bin/env python3.12
"""Shared URL scheme guard for every urllib.request.urlopen caller.

CodeFactor security finding "Audit url open for permitted schemes": all
registry tooling that opens URLs must reject non-http(s) schemes (file:/,
custom schemes) before calling urlopen. Keeping the guard in one module
mirrors the shared-constant pattern of archive_formats.py.
"""

from urllib.parse import urlparse

#: URL schemes permitted for artifact/manifest downloads.
HTTP_SCHEMES = frozenset({"https", "http"})


def ensure_http_url(url: str) -> None:
    """Raise ValueError unless *url* is an http(s) URL with a host.

    Parses with :func:`urllib.parse.urlparse` so the scheme check is
    case-insensitive (``HTTPS://`` and ``HtTp://`` pass) and rejects
    hostless or scheme-confusable forms such as ``https:evil.com`` or a bare
    ``https://``, which urlopen would otherwise open with unexpected
    semantics (e.g. local file reads) — the behavior CodeFactor's S310
    finding warns about.
    """
    if not isinstance(url, str):
        raise ValueError(f"URL must use http(s), got {url!r}")
    parsed = urlparse(url)
    try:
        has_host = parsed.hostname is not None
    except ValueError:
        # Malformed IPv6-style host (e.g. an unclosed '['); treat as no host.
        has_host = False
    if parsed.scheme.lower() not in HTTP_SCHEMES or not has_host:
        raise ValueError(f"URL must use http(s), got {url!r}")
