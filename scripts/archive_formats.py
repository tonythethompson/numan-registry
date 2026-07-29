#!/usr/bin/env python3.12
"""Shared archive-format declarations for intake validation and docs."""

# Keep this tuple aligned with ArchiveFormat::from_url in Numan's
# src/install/extract.rs; unsupported suffixes fail during client install.
SUPPORTED_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar.gz",
    ".tgz",
    ".tar.xz",
    ".txz",
    ".tar",
)

_MARKDOWN_SUFFIXES = [f"`{suffix}`" for suffix in SUPPORTED_ARCHIVE_SUFFIXES]
SUPPORTED_ARCHIVE_SUFFIXES_MARKDOWN = (
    ", ".join(_MARKDOWN_SUFFIXES[:-1]) + f", or {_MARKDOWN_SUFFIXES[-1]}"
)
