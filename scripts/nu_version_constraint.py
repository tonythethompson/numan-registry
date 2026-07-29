#!/usr/bin/env python3.12
"""Validate exact Nu versions against Numan's supported constraint forms."""

from __future__ import annotations

import re

EXACT_NU_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
COMPARATOR = re.compile(r"^(>=|<=|>|<|=)(.+)$")
MINOR_WILDCARD = re.compile(
    r"^=?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(?:x|X|\*)$"
)


def parse_exact_nu_version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or EXACT_NU_VERSION.fullmatch(value) is None:
        raise ValueError(
            f"{value!r} is not an exact Nu version (expected MAJOR.MINOR.PATCH)"
        )
    return tuple(int(part) for part in value.split("."))


def matches_nu_constraint(version: str, constraint: str) -> bool:
    """Match the exact version using the constraint forms understood by Numan."""
    candidate = parse_exact_nu_version(version)
    if constraint == "*":
        return True
    if not isinstance(constraint, str) or not constraint.strip():
        raise ValueError("nu_version constraint must be a non-empty string")

    for token in constraint.split():
        wildcard = MINOR_WILDCARD.fullmatch(token)
        if wildcard is not None:
            if candidate[:2] != tuple(int(part) for part in wildcard.groups()):
                return False
            continue

        comparator = COMPARATOR.fullmatch(token)
        if comparator is None:
            required = parse_exact_nu_version(token)
            if candidate != required:
                return False
            continue

        operator, required_text = comparator.groups()
        required = parse_exact_nu_version(required_text)
        if operator == ">=" and not candidate >= required:
            return False
        if operator == ">" and not candidate > required:
            return False
        if operator == "<=" and not candidate <= required:
            return False
        if operator == "<" and not candidate < required:
            return False
        if operator == "=" and not candidate == required:
            return False
    return True


def lifecycle_evidence_error(constraint: str, evidence) -> str | None:
    if not isinstance(evidence, list) or not evidence:
        return "verified_with must contain at least one exact Nu version"
    for version in evidence:
        try:
            compatible = matches_nu_constraint(version, constraint)
        except ValueError as exc:
            return str(exc)
        if not compatible:
            return f"verified_with version {version!r} does not satisfy {constraint!r}"
    return None
