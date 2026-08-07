#!/usr/bin/env python3.12
"""Tests for scripts/measure_complexity.py."""

from __future__ import annotations

import textwrap
import unittest

from measure_complexity import analyze_file, analyze_source, complexity_of

import ast


def _parse_expr(source: str) -> ast.AST:
    return ast.parse(source).body[0]


class TestComplexityOf(unittest.TestCase):
    """Unit tests for the McCabe counter on individual statements."""

    def test_plain_expression_is_1(self):
        expr = _parse_expr("x = 1 + 2")
        self.assertEqual(complexity_of(expr), 1)

    def test_single_if_adds_1(self):
        node = _parse_expr(
            "if x:\n"
            "    y = 1\n"
        )
        self.assertEqual(complexity_of(node), 2)

    def test_nested_ifs(self):
        node = _parse_expr(
            "if a:\n"
            "    if b:\n"
            "        y = 1\n"
        )
        self.assertEqual(complexity_of(node), 3)

    def test_for_adds_1(self):
        node = _parse_expr(
            "for i in xs:\n"
            "    y = i\n"
        )
        self.assertEqual(complexity_of(node), 2)

    def test_elif_counts_as_decision(self):
        node = _parse_expr(
            "if a:\n"
            "    x = 1\n"
            "elif b:\n"
            "    x = 2\n"
        )
        self.assertEqual(complexity_of(node), 3)

    def test_boolop_counts_operands_minus_one(self):
        node = _parse_expr("if a and b:\n    x = 1")
        self.assertEqual(complexity_of(node), 3)  # if + and
        node = _parse_expr("if a and b and c:\n    x = 1")
        self.assertEqual(complexity_of(node), 4)  # if + two ands

    def test_while_and_assert(self):
        node = _parse_expr(
            "while x < 10:\n"
            "    assert x\n"
            "    x += 1\n"
        )
        self.assertEqual(complexity_of(node), 3)

    def test_try_except(self):
        node = _parse_expr(
            "try:\n"
            "    x = 1\n"
            "except ValueError:\n"
            "    x = 2\n"
            "except TypeError:\n"
            "    x = 3\n"
        )
        self.assertEqual(complexity_of(node), 3)  # two except handlers

    def test_ternary_ifexp(self):
        node = _parse_expr("x = 1 if cond else 2")
        self.assertEqual(complexity_of(node), 2)

    def test_comprehension_counts(self):
        node = _parse_expr("xs = [i for i in range(10)]")
        self.assertEqual(complexity_of(node), 2)

    def test_async_for_counts(self):
        node = _parse_expr(
            "async for i in xs:\n"
            "    y = i\n"
        )
        self.assertEqual(complexity_of(node), 2)

    def test_async_with_counts(self):
        node = _parse_expr(
            "async with lock:\n"
            "    y = 1\n"
        )
        self.assertEqual(complexity_of(node), 2)


class TestAnalyzeSource(unittest.TestCase):
    """Tests for source-level analysis."""

    def test_reports_function_locations(self):
        source = textwrap.dedent(
            """\
            def simple():
                return 1

            def branched(x):
                if x:
                    return 1
                return 0

            async def coro():
                pass
            """
        )
        functions = analyze_source(source)
        by_name = {fn.name: fn for fn in functions}
        self.assertEqual(by_name["simple"].complexity, 1)
        self.assertEqual(by_name["branched"].complexity, 2)
        self.assertEqual(by_name["branched"].lineno, 4)
        self.assertEqual(by_name["branched"].end_lineno, 7)
        self.assertIn("coro", by_name)

    def test_nested_functions_included(self):
        source = textwrap.dedent(
            """\
            def outer(x):
                def inner(y):
                    if y:
                        return 1
                    return 0
                return inner(x)
            """
        )
        functions = analyze_source(source)
        names = {fn.name for fn in functions}
        self.assertIn("outer", names)
        self.assertIn("inner", names)

    def test_outer_excludes_nested_function_complexity(self):
        # Like mccabe, each function is measured independently: inner's if
        # must not inflate outer's complexity.
        source = textwrap.dedent(
            """\
            def outer(x):
                def inner(y):
                    if y:
                        return 1
                    return 0
                if x:
                    return inner(x)
                return 0
            """
        )
        functions = analyze_source(source)
        by_name = {fn.name: fn for fn in functions}
        self.assertEqual(by_name["inner"].complexity, 2)
        self.assertEqual(by_name["outer"].complexity, 2)  # outer if only

    def test_analyze_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
            functions = analyze_file(path)
            self.assertEqual(len(functions), 1)
            self.assertEqual(functions[0].name, "f")
            self.assertEqual(functions[0].complexity, 2)


class TestCLI(unittest.TestCase):
    """Tests for the command-line entry point."""

    def test_min_filter(self):
        import tempfile
        from pathlib import Path
        from io import StringIO
        from contextlib import redirect_stdout

        import measure_complexity

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "def simple():\n    return 1\n\n"
                "def complex_fn(x):\n    if x:\n        return 1\n    return 0\n"
            )
            buf = StringIO()
            with redirect_stdout(buf):
                rc = measure_complexity.main([str(path), "--min", "2"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("complex_fn", out)
            self.assertNotIn("simple", out)

    def test_returns_1_on_missing_file(self):
        import measure_complexity

        rc = measure_complexity.main(["/nonexistent/file.py"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
