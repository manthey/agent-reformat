"""Tests for AR003: Strip single leading underscores from class methods."""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class TestAR003FixMode:
    """In fix mode AR003 strips underscore from class methods using a bare call."""

    def test_method_stripped_when_used(self, tmp_path, reformat) -> None:
        """A method with single leading underscore gets renamed when called."""
        src = (
            'class Foo:\n'
            '\n'
            '    def _helper():\n'
            '\n'
            '        pass\n'
            '\n'
            '_helper()\n'  # bare Name call -> triggers AR003 stripping
        )
        res = reformat.fix(src)
        after = res.after
        assert 'def helper()' in after
        assert '_helper' not in after

    def test_unused_method_not_stripped(self, tmp_path, reformat) -> None:
        """A method with no Load nodes for its name stays underscored."""
        src = (
            'class Foo:\n'
            '\n'
            '    def _orphan():\n'
            '\n'
            '        pass\n'  # no call -> not stripped
        )
        res = reformat.fix(src)
        after = res.after
        assert '_orphan' in after

    def test_clean_method_not_modified(self, tmp_path, reformat) -> None:
        """Methods without underscore are untouched."""
        src = (
            'class Foo:\n'
            '\n'
            '    def helper():\n'
            '\n'
            '        pass\n'
            '\n'
            'helper()\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert 'def helper()' in after


class TestAR003CheckMode:
    """In check mode AR003 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path, reformat) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def _x():\n'
            '\n'
            '        pass\n'
            '\n'
            '_x()\n'
        )
        res = reformat.check(src)
        stdout, rc = res.stdout, res.rc
        assert rc != 0
        assert 'AR003' in stdout

    def test_clean_file_no_violation(self, tmp_path, reformat) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def x():\n'
            '\n'
            '        pass\n'
            '\n'
            'x()\n'
        )
        res = reformat.check(src, 'AR003')
        rc = res.rc
        assert rc == 0


class TestAR003NoqaProtection:
    """Verify noqa directives suppress AR003 stripping."""

    def test_bare_noqa_on_def(self, tmp_path, reformat) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def _x():  # noqa: AR003\n'
            '\n'
            '        pass\n'
            '\n'
            '_x()\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert '_x' in after

    def test_noqa_on_call_site(self, tmp_path, reformat) -> None:
        """Noqa on the bare call site also protects."""
        src = (
            'class Foo:\n'
            '\n'
            '    def _helper():\n'
            '\n'
            '        pass\n'
            '\n'
            '_helper()  # noqa\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert '_helper' in after


class TestAR003EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_method_preserved(self, tmp_path, reformat) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def __init__():\n'
            '\n'
            '        pass\n'
        )  # dunder -> skipped by code logic
        res = reformat.fix(src)
        after = res.after
        assert '__init__' in after

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        """Identifiers starting with __ are never stripped."""
        src = (
            'class Foo:\n'
            '\n'
            '    def __helper():\n'
            '\n'
            '        pass\n'
            '\n'
            '__helper()\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert '__helper' in after

    def test_trailing_underscore_preserved(self, tmp_path, reformat) -> None:
        """Methods ending with underscore like 'cls_' stay."""
        src = (
            'class Foo:\n'
            '\n'
            '    def cls_():\n'
            '\n'
            '        pass\n'
            '\n'
            'cls_()\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert 'cls_' in after


class TestAR003AsyncMethods:
    """Async methods in classes should follow the same AR003 rules."""

    def test_async_method_stripped_when_used(self, tmp_path, reformat) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    async def _fetch():\n'
            '\n'
            '        pass\n'
            '\n'
            '_fetch()\n'
        )
        res = reformat.fix(src)
        after = res.after
        assert 'async def fetch()' in after
