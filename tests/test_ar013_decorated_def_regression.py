"""Regression tests for AR013 bug: blank lines before decorated defs removed.

AR013 must never remove the blank lines between a statement and a
function/class definition (including its decorators).  See the case at
paper_search.py L561-L566 in manthey/utils, where the blank line before
'@sleep_and_retry' of the 'search' method was being deleted by AR013.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> str:
    """Run agent-reformat in fix mode with AR013 only; returns new content."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR013'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return f.read_text()


def run_check(tmp_path: Path, source_code: str) -> tuple[str, int]:
    """Run agent-reformat in check mode; returns (stdout, exit code)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = io.StringIO()
    rc = 0
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--rules', 'AR013'])
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return captured.getvalue(), rc


SRC_CLASS_DECORATED = (
    'class A:\n'
    '    def old(self, x):\n'
    "        base = 'x'\n"
    '        mid = [base]\n'
    '        e = [mid]\n'
    '\n'
    '\n'
    'class B:\n'
    '    m = [1]\n'
    "    n = 'x'\n"
    '\n'
    '    @deco\n'
    '    def f(self, q):\n'
    '        g = [q]\n'
    '        h = [g]\n'
    "        k = 'end' + g[0]\n"
    '\n'
    '\n'
    'class C:\n'
    "    w = 'w'\n"
    '    d = [w]\n'
    '    def m2(self, a, b):\n'
    '        p = [w]\n'
    '        qq = [p]\n'
    '        r = [qq]\n'
    "        note = 'alpha'\n"
    "        z = [n, 'z']\n"
    '        return z\n'
)


class TestAR013DecoratedDefRegression:
    """Blank lines above def/class definitions (with decorators) survive AR013."""

    def test_blank_before_decorated_method_preserved(self, tmp_path: Path) -> None:
        """The blank between a class attribute and '@deco' must be preserved."""
        after = run_fix(tmp_path, SRC_CLASS_DECORATED)
        assert after == SRC_CLASS_DECORATED

    def test_check_mode_no_ar013_violation(self, tmp_path: Path) -> None:
        """No AR013 violation may be reported for the source above."""
        stdout, rc = run_check(tmp_path, SRC_CLASS_DECORATED)
        assert 'AR013' not in stdout
        assert rc == 0

    def test_paper_search_shape_preserved(self, tmp_path: Path) -> None:
        """Mirror of the reported case in manthey/utils paper_search.py."""
        src = (
            'class OpenAlexBackend(ArchiveBackend):\n'
            "    name = 'openalex'\n"
            '    def search(self, query_terms, max_results):\n'
            '        return []\n'
            '\n'
            '\n'
            'class SemanticScholarBackend(ArchiveBackend):\n'
            "    name = 'semantic_scholar'\n"
            '\n'
            '    @sleep_and_retry\n'
            '    @limits(calls=1, period=1)\n'
            '    def search(self, query_terms, max_results):\n'
            '        papers = []\n'
            '        flat_terms = []\n'
            '        return papers + flat_terms\n'
        )
        after = run_fix(tmp_path, src)
        assert "name = 'semantic_scholar'\n\n    @sleep_and_retry\n" in after
