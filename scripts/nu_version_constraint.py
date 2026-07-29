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
    """
    Parse an exact Nu version into its numeric components.
    
    Parameters:
        value (str): Version in MAJOR.MINOR.PATCH format.
    
    Returns:
        tuple[int, int, int]: The major, minor, and patch components.
    
    Raises:
        ValueError: If value is not an exact Nu version.
    """
    if not isinstance(value, str) or EXACT_NU_VERSION.fullmatch(value) is None:
        raise ValueError(
            f"{value!r} is not an exact Nu version (expected MAJOR.MINOR.PATCH)"
        )
    return tuple(int(part) for part in value.split("."))


def matches_nu_constraint(version: str, constraint: str) -> bool:
    """
    Determine whether an exact Nu version satisfies a supported constraint expression.
    
    Parameters:
        version (str): Exact version in `MAJOR.MINOR.PATCH` format.
        constraint (str): Wildcard, exact-version, comparator, or space-separated constraint expression.
    
    Returns:
        bool: `True` if the version satisfies every constraint, `False` otherwise.
    
    Raises:
        ValueError: If the version or constraint contains an invalid value.
    """
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
    """
    Validate lifecycle evidence against a Nu version constraint.
    
    Parameters:
        constraint (str): Constraint that each evidence version must satisfy.
        evidence (list): Exact Nu versions used as lifecycle evidence.
    
    Returns:
        str | None: An error message for missing, invalid, or incompatible evidence; `None` when all evidence satisfies the constraint.
    """
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
