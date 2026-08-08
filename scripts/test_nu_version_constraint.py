#!/usr/bin/env python3.12
"""Tests for scripts/nu_version_constraint.py."""

from __future__ import annotations

import unittest

import nu_version_constraint as nvc


class TestParseExactNuVersion(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(nvc.parse_exact_nu_version("0.114.0"), (0, 114, 0))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            nvc.parse_exact_nu_version("0.114")


class TestMatchesNuConstraint(unittest.TestCase):

    def test_wildcard_star(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", "*"))
        self.assertTrue(nvc.matches_nu_constraint("0.9.9", "*"))

    def test_exact_match(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", "0.114.0"))

    def test_exact_mismatch(self):
        self.assertFalse(nvc.matches_nu_constraint("0.114.0", "0.113.0"))

    def test_comparators(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", ">=0.114.0"))
        self.assertTrue(nvc.matches_nu_constraint("0.114.1", ">=0.114.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.113.9", ">=0.114.0"))
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", ">0.113.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.113.0", ">0.113.0"))
        self.assertTrue(nvc.matches_nu_constraint("0.113.0", "<=0.114.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.115.0", "<=0.114.0"))
        self.assertTrue(nvc.matches_nu_constraint("0.113.0", "<0.114.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.114.0", "<0.114.0"))
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", "=0.114.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.114.1", "=0.114.0"))

    def test_minor_wildcard(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.5", "0.114.x"))
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", "0.114.*"))
        self.assertFalse(nvc.matches_nu_constraint("0.113.5", "0.114.x"))

    def test_equals_prefixed_wildcard_routes_to_wildcard(self):
        # '=0.114.x' matches MINOR_WILDCARD (optional '=' prefix) and must not
        # fall through to COMPARATOR's '=' branch (which would raise on 'x').
        self.assertTrue(nvc.matches_nu_constraint("0.114.5", "=0.114.x"))
        self.assertFalse(nvc.matches_nu_constraint("0.113.5", "=0.114.x"))

    def test_space_separated_combination(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.3", ">=0.114.0 <0.115.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.115.0", ">=0.114.0 <0.115.0"))
        self.assertFalse(nvc.matches_nu_constraint("0.113.0", ">=0.114.0 <0.115.0"))

    def test_mixed_tokens(self):
        self.assertTrue(nvc.matches_nu_constraint("0.114.0", ">=0.114.0 0.114.x"))
        self.assertFalse(nvc.matches_nu_constraint("0.114.1", "0.114.0 0.114.x"))

    def test_empty_constraint_raises(self):
        with self.assertRaises(ValueError):
            nvc.matches_nu_constraint("0.114.0", "")
        with self.assertRaises(ValueError):
            nvc.matches_nu_constraint("0.114.0", "   ")

    def test_invalid_version_raises(self):
        with self.assertRaises(ValueError):
            nvc.matches_nu_constraint("not-a-version", "*")


class TestTokenHelpers(unittest.TestCase):

    def test_matches_minor_wildcard(self):
        self.assertTrue(nvc._matches_minor_wildcard((0, 114, 0), "0.114.x"))
        self.assertFalse(nvc._matches_minor_wildcard((0, 113, 0), "0.114.x"))

    def test_matches_minor_wildcard_bad_token(self):
        with self.assertRaises(ValueError):
            nvc._matches_minor_wildcard((0, 114, 0), ">=0.114.0")

    def test_matches_exact(self):
        self.assertTrue(nvc._matches_exact((0, 114, 0), "0.114.0"))
        self.assertFalse(nvc._matches_exact((0, 114, 1), "0.114.0"))

    def test_matches_comparator_ops(self):
        candidate = (0, 114, 0)
        self.assertTrue(nvc._matches_comparator(candidate, ">=", "0.114.0"))
        self.assertFalse(nvc._matches_comparator(candidate, ">", "0.114.0"))
        self.assertTrue(nvc._matches_comparator(candidate, "<=", "0.114.0"))
        self.assertFalse(nvc._matches_comparator(candidate, "<", "0.114.0"))
        self.assertTrue(nvc._matches_comparator(candidate, "=", "0.114.0"))

    def test_matches_comparator_bad_version(self):
        with self.assertRaises(ValueError):
            nvc._matches_comparator((0, 114, 0), ">=", "bogus")

    def test_token_matches_dispatches_by_form(self):
        candidate = (0, 114, 5)
        self.assertTrue(nvc._token_matches(candidate, "0.114.x"))
        self.assertTrue(nvc._token_matches(candidate, ">=0.114.0"))
        self.assertTrue(nvc._token_matches(candidate, "0.114.5"))
        self.assertFalse(nvc._token_matches(candidate, "0.113.0"))


if __name__ == "__main__":
    unittest.main()
