#!/usr/bin/env python3.12
"""Unit checks for scripts/url_safety.py (no network)."""

from __future__ import annotations

import sys
import unittest
import urllib.request
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "url_safety.py"
if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

from url_safety import (  # noqa: E402
    ensure_http_url,
    fork_upstream_differs_from_git,
    github_repo_key,
    http_opener,
)


class EnsureHttpUrlTests(unittest.TestCase):
    def test_accepts_https(self):
        self.assertIsNone(ensure_http_url("https://example.com/a.zip"))

    def test_accepts_http(self):
        self.assertIsNone(ensure_http_url("http://example.com/a.zip"))

    def test_accepts_uppercase_scheme(self):
        self.assertIsNone(ensure_http_url("HTTPS://example.com/a.zip"))
        self.assertIsNone(ensure_http_url("HTTP://example.com/a.zip"))

    def test_accepts_mixed_case_scheme(self):
        self.assertIsNone(ensure_http_url("HtTp://example.com/a.zip"))
        self.assertIsNone(ensure_http_url("HttPs://example.com/a.zip"))

    def test_accepts_ipv6_host(self):
        self.assertIsNone(ensure_http_url("https://[::1]/a.zip"))

    def test_accepts_host_with_port_and_userinfo(self):
        self.assertIsNone(ensure_http_url("https://example.com:8443/a.zip"))
        self.assertIsNone(ensure_http_url("https://user:pass@example.com/a.zip"))

    def test_rejects_file_scheme(self):
        with self.assertRaises(ValueError):
            ensure_http_url("file:///etc/passwd")

    def test_rejects_custom_scheme(self):
        with self.assertRaises(ValueError):
            ensure_http_url("ftp://example.com/a.zip")

    def test_rejects_missing_scheme(self):
        with self.assertRaises(ValueError):
            ensure_http_url("example.com/a.zip")

    def test_rejects_scheme_without_double_slash(self):
        # 'https:evil.com' parses with scheme='https' but no authority;
        # urlopen would not open it as https, so the guard must reject it.
        with self.assertRaises(ValueError):
            ensure_http_url("https:evil.com")

    def test_rejects_missing_host(self):
        with self.assertRaises(ValueError):
            ensure_http_url("https://")

    def test_rejects_authority_without_hostname(self):
        with self.assertRaises(ValueError):
            ensure_http_url("https://@/a.zip")

    def test_rejects_malformed_ipv6(self):
        with self.assertRaises(ValueError):
            ensure_http_url("https://[::1")

    def test_rejects_empty_string(self):
        with self.assertRaises(ValueError):
            ensure_http_url("")

    def test_rejects_non_string(self):
        with self.assertRaises(ValueError):
            ensure_http_url(None)  # type: ignore[arg-type]


class GitHubRepoKeyTests(unittest.TestCase):
    def test_normalizes_plain_and_git_suffix(self):
        self.assertEqual(
            github_repo_key("https://github.com/Owner/Repo"),
            "owner/repo",
        )
        self.assertEqual(
            github_repo_key("https://github.com/Owner/Repo.git"),
            "owner/repo",
        )
        self.assertEqual(
            github_repo_key("https://www.github.com/Owner/Repo.GIT/"),
            "owner/repo",
        )

    def test_decodes_percent_encoded_git_suffix(self):
        self.assertEqual(
            github_repo_key("https://github.com/numan-maintained/pkg%2Egit"),
            "numan-maintained/pkg",
        )
        self.assertEqual(
            github_repo_key("https://github.com/numan-maintained/pkg%2egit"),
            "numan-maintained/pkg",
        )
        self.assertEqual(
            github_repo_key("https://github.com/numan-maintained/pkg%2E%67%69%74"),
            "numan-maintained/pkg",
        )

    def test_rejects_non_github_hosts(self):
        self.assertIsNone(github_repo_key("https://gitlab.com/owner/repo"))
        self.assertIsNone(github_repo_key("https://example.com/owner/repo.git"))

    def test_decodes_percent_encoded_path_separator(self):
        # An encoded "/" (%2F) must not hide an extra path segment from the
        # split -- decoding after split let "pkg%2Fissues" masquerade as a
        # distinct repo "pkg/issues" instead of resolving to "pkg".
        self.assertEqual(
            github_repo_key("https://github.com/numan-maintained/pkg%2Fissues"),
            "numan-maintained/pkg",
        )


class ForkUpstreamDiffersTests(unittest.TestCase):
    def test_same_repo_with_encoded_git_suffix_is_not_different(self):
        git = "https://github.com/numan-maintained/pkg"
        upstream = "https://github.com/numan-maintained/pkg%2Egit"
        self.assertFalse(fork_upstream_differs_from_git(git, upstream))

    def test_same_repo_with_encoded_path_separator_is_not_different(self):
        git = "https://github.com/numan-maintained/pkg"
        upstream = "https://github.com/numan-maintained/pkg%2Fissues"
        self.assertFalse(fork_upstream_differs_from_git(git, upstream))

    def test_distinct_repos_remain_different(self):
        git = "https://github.com/numan-maintained/pkg"
        upstream = "https://github.com/original-author/pkg"
        self.assertTrue(fork_upstream_differs_from_git(git, upstream))


class HttpOnlyRedirectHandlerTests(unittest.TestCase):
    """The shared opener must re-validate every redirect target."""

    def _redirect_handler(self):
        opener = http_opener()
        return next(
            h for h in opener.handlers
            if isinstance(h, urllib.request.HTTPRedirectHandler)
        )

    def test_redirect_to_file_scheme_rejected(self):
        handler = self._redirect_handler()
        req = urllib.request.Request("https://example.com/a.zip")
        with self.assertRaises(ValueError):
            handler.redirect_request(
                req, None, 302, "Found", {}, "file:///etc/passwd"
            )

    def test_redirect_to_http_scheme_allowed(self):
        handler = self._redirect_handler()
        req = urllib.request.Request("https://example.com/a.zip")
        new_req = handler.redirect_request(
            req, None, 302, "Found", {}, "https://cdn.example.com/b.zip"
        )
        self.assertEqual(new_req.full_url, "https://cdn.example.com/b.zip")

    def test_redirect_to_hostless_https_rejected(self):
        handler = self._redirect_handler()
        req = urllib.request.Request("https://example.com/a.zip")
        with self.assertRaises(ValueError):
            handler.redirect_request(
                req, None, 302, "Found", {}, "https://"
            )


if __name__ == "__main__":
    unittest.main()
