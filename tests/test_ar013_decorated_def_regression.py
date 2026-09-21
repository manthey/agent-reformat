"""Regression tests for AR013 bug: blank lines before decorated defs removed.

AR013 must never remove the blank lines between a statement and a
function/class definition (including its decorators).  See the case at
paper_search.py L561-L566 in manthey/utils, where the blank line before
'@sleep_and_retry' of the 'search' method was being deleted by AR013.
"""
from __future__ import annotations

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

    def test_blank_before_decorated_method_preserved(self, tmp_path, reformat) -> None:
        """The blank between a class attribute and '@deco' must be preserved."""
        after = reformat.fix(SRC_CLASS_DECORATED, 'AR013').after
        assert after == SRC_CLASS_DECORATED

    def test_check_mode_no_ar013_violation(self, tmp_path, reformat) -> None:
        """No AR013 violation may be reported for the source above."""
        res = reformat.check(SRC_CLASS_DECORATED, 'AR013')
        stdout, rc = res.stdout, res.rc
        assert 'AR013' not in stdout
        assert rc == 0

    def test_paper_search_shape_preserved(self, tmp_path, reformat) -> None:
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
        after = reformat.fix(src, 'AR013').after
        assert "name = 'semantic_scholar'\n\n    @sleep_and_retry\n" in after
