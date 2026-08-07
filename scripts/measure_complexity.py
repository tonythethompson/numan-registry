#!/usr/bin/env python3.12
"""Measure cyclomatic complexity of functions in Python files.

Dev utility for tracking CodeFactor-style \"Complex Method\" findings
(e.g. the open items in issue #42). Uses an ``ast``-based counter that
mirrors mccabe's counting rules: base 1, plus 1 for each if/elif, for,
while, except, with, assert, ternary-if, bool-op branch, and
comprehension.

Usage:
  python scripts/measure_complexity.py [FILES...] [--min 15]
  python scripts/measure_complexity.py scripts/*.py --min 15
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionComplexity:
    """Cyclomatic complexity and location of a single function."""

    name: str
    lineno: int
    end_lineno: int
    complexity: int


class McCabeCounter(ast.NodeVisitor):
    """Count cyclomatic complexity using mccabe-compatible rules.

    Base complexity is 1. Each decision point adds 1: ``if``/``elif``,
    ``for``, ``while``, ``except``, ``with``, ``assert``, ternary
    ``if/else`` expressions, each ``and``/``or`` operand pair, and each
    comprehension (list/set/dict/generator).
    """

    def __init__(self) -> None:
        self.complexity = 1

    def _bump(self, node: ast.AST) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        return self._bump(node)

    def visit_For(self, node: ast.For) -> None:
        return self._bump(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        return self._bump(node)

    def visit_While(self, node: ast.While) -> None:
        return self._bump(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        return self._bump(node)

    def visit_With(self, node: ast.With) -> None:
        return self._bump(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        return self._bump(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        return self._bump(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        return self._bump(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        return self._bump(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        return self._bump(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        return self._bump(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        return self._bump(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Like mccabe, count each function independently: walk this function's
        # own body statements but do not descend into nested defs/classes.
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            self.visit(stmt)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Methods are counted as separate functions; a class body adds no
        # decision points of its own.
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            self.visit(stmt)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


def complexity_of(node: ast.AST) -> int:
    """Return the cyclomatic complexity of a single AST node."""
    counter = McCabeCounter()
    counter.visit(node)
    return counter.complexity


def analyze_source(source: str, filename: str = "<string>") -> list[FunctionComplexity]:
    """Return complexity for every function/async-function in ``source``.

    Args:
        source: Python source code.
        filename: Label used in syntax-error messages.

    Returns:
        FunctionComplexity entries in source order (top-level first, then
        nested definitions as they appear).
    """
    tree = ast.parse(source, filename=filename)
    results: list[FunctionComplexity] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            results.append(
                FunctionComplexity(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=node.end_lineno or node.lineno,
                    complexity=complexity_of(node),
                )
            )
    return results


def analyze_file(path: Path) -> list[FunctionComplexity]:
    """Return complexity for every function in a Python file."""
    return analyze_source(path.read_text(encoding="utf-8"), filename=str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path, help="Python files to analyze")
    parser.add_argument(
        "--min",
        type=int,
        default=1,
        help="Only report functions with complexity >= this value (default: 1)",
    )
    parser.add_argument(
        "--sort",
        action="store_true",
        help="Sort output by complexity descending",
    )
    args = parser.parse_args(argv)

    rows: list[tuple[str, FunctionComplexity]] = []
    for path in args.files:
        try:
            functions = analyze_file(path)
        except (OSError, SyntaxError) as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            return 1
        for fn in functions:
            if fn.complexity >= args.min:
                rows.append((str(path), fn))

    if args.sort:
        rows.sort(key=lambda item: item[1].complexity, reverse=True)

    for path, fn in rows:
        print(
            f"{path}:{fn.lineno}-{fn.end_lineno} {fn.name} "
            f"cc={fn.complexity}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
