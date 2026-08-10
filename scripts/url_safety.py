#!/usr/bin/env python3.12
"""Shared URL scheme guard for every urllib.request.urlopen caller.

CodeFactor security finding "Audit url open for permitted schemes": all
registry tooling that opens URLs must reject non-http(s) schemes (file:/,
custom schemes) before calling urlopen, and must not follow a redirect
that leaves the http(s) allowlist. Keeping the guard in one module
mirrors the shared-constant pattern of archive_formats.py.
"""

import urllib.request
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


def github_repo_key(url: str) -> str | None:
    """Return ``owner/name`` for a GitHub http(s) URL, else ``None``."""
    parsed = urlparse(url.strip().rstrip("/"))
    if parsed.scheme.lower() not in HTTP_SCHEMES:
        return None
    host = (parsed.hostname or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}".lower()


def fork_upstream_differs_from_git(git: str, upstream: str) -> bool:
    """Return whether *upstream* identifies a different repo than *git*."""
    git_key = github_repo_key(git)
    upstream_key = github_repo_key(upstream)
    if git_key and upstream_key:
        return git_key != upstream_key
    return git.strip().rstrip("/").lower() != upstream.strip().rstrip("/").lower()


class _HttpOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject any redirect whose target fails the http(s) scheme guard.

    urllib's default opener follows redirects with the full handler chain,
    so a ``https:`` response that redirects to ``file:///etc/passwd`` would
    otherwise be fetched locally. This handler runs every ``newurl`` through
    :func:`ensure_http_url` before delegating to the standard handler.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ensure_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_opener() -> urllib.request.OpenerDirector:
    """Return an opener whose redirects are also constrained to http(s).

    Callers should use ``http_opener().open(req, timeout=N)`` instead of
    ``urllib.request.urlopen`` so the initial request AND every redirect
    target pass :func:`ensure_http_url`.
    """
    return urllib.request.build_opener(_HttpOnlyRedirectHandler())
