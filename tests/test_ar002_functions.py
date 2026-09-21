"""Tests for AR002: Strip single leading underscores from top-level functions."""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class TestAR002FixMode:
    """In fix mode, AR002 strips underscore from top-level functions."""

    def test_strippable_func_is_renamed(self, tmp_path, reformat) -> None:
        src = 'def _helper():\n\n    pass\n\n_helper()\n'
        after = reformat.fix(src).after
        assert 'def helper()' in after
        assert '_helper' not in after

    def test_unused_func_not_stripped(self, tmp_path, reformat) -> None:
        """A function with no Load nodes for its name stays underscored."""
        src = 'def _orphan():\n\n    pass\n'
        after = reformat.fix(src).after
        assert '_orphan' in after

    def test_async_func_stripped_when_used(self, tmp_path, reformat) -> None:
        src = 'async def _work():\n\n    pass\n\n_work()\n'
        res = reformat.fix(src)
        after = res.after
        assert 'async def work()' in after

    def test_clean_func_not_modified(self, tmp_path, reformat) -> None:
        """Functions without leading underscore are untouched."""
        src = 'def helper():\n\n    pass\n'
        after = reformat.fix(src).after
        assert 'helper()' in after


class TestAR002CheckMode:
    """In check mode, AR002 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path, reformat) -> None:
        res = reformat.check('def _x():\n\n    pass\n_x()\n')
        stdout, rc = res.stdout, res.rc
        assert rc != 0
        assert 'AR002' in stdout

    def test_clean_file_no_violation(self, tmp_path, reformat) -> None:
        res = reformat.check('def x():\n\n    pass\nx()\n', 'AR002')
        rc = res.rc
        assert rc == 0


class TestAR002NoqaProtection:
    """Verify noqa directives suppress AR002 stripping."""

    def test_bare_noqa_on_def(self, tmp_path, reformat) -> None:
        src = 'def _x():\n\n    pass\n_x()  # noqa: AR002\n'
        after = reformat.fix(src).after
        assert '_x' in after

    def test_noqa_on_def_line(self, tmp_path, reformat) -> None:
        """Bare # noqa suppresses all violations for nearby lines."""
        res = reformat.check('x  # noqa\n')
        stdout, rc = res.stdout, res.rc
        assert rc == 0
        assert not stdout.strip()


class TestAR002EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_preserved(self, tmp_path, reformat) -> None:
        src = 'def __version__():\n\n    pass\n'  # dunder -> skipped by code
        res = reformat.check(src, 'AR002')
        rc = res.rc
        assert '__version__' in src
        assert rc == 0

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        """Identifiers starting with __ are never stripped."""
        src = 'def __internal():\n\n    pass\n_x()\n'
        after = reformat.fix(src).after
        assert '__internal' in after

    def test_trailing_underscore_preserved(self, tmp_path, reformat) -> None:
        """Identifiers ending with underscore like 'cls_' stay."""
        src = 'def cls_():\n\n    pass\ncls_()\n'
        after = reformat.fix(src).after
        assert 'cls_' in after


class TestAR002AsyncFunctions:
    """Top-level async functions should follow the same AR002 rules."""

    def test_async_func_with_underscore_stripped(self, tmp_path, reformat) -> None:
        src = 'async def _fetch():\n\n    pass\n\n_fetch()\n'
        res = reformat.fix(src)
        after = res.after
        assert 'async def fetch()' in after
