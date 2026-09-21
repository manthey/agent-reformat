"""Tests for AR004: Strip single leading underscores from nested functions."""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class TestAR004FixMode:
    """In fix mode, AR004 strips underscore from nested functions."""

    def test_nested_func_in_top_level_fn_stripped(self, tmp_path, reformat) -> None:
        """Nested function inside top-level function has underscore stripped."""
        src = """def outer():
    def _inner():
        pass
    _inner()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'def inner()' in after
        assert '_inner' not in after

    def test_nested_func_in_class_method_stripped(self, tmp_path, reformat) -> None:
        """Nested function inside class method has underscore stripped."""
        src = """class Foo:
    def method(self):
        def _inner():
            pass
        _inner()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'def inner()' in after
        assert '_inner' not in after

    def test_unused_nested_func_not_stripped(self, tmp_path, reformat) -> None:
        """Unused nested function is NOT stripped (no Load nodes)."""
        src = """def outer():
    def _orphan():
        pass
"""
        res = reformat.fix(src)
        after = res.after
        assert '_orphan' in after

    def test_clean_nested_func_not_modified(self, tmp_path, reformat) -> None:
        """Nested function without underscore is untouched."""
        src = """def outer():
    def inner():
        pass
    inner()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'def inner()' in after


class TestAR004CheckMode:
    """In check mode, AR004 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path, reformat) -> None:
        src = """def outer():
    def _x():
        pass
_x()
"""
        res = reformat.check(src)
        stdout, rc = res.stdout, res.rc
        assert rc != 0
        assert 'AR004' in stdout

    def test_clean_file_no_violation(self, tmp_path, reformat) -> None:
        src = """def outer():
    def x():
        pass
x()
"""
        res = reformat.check(src)
        rc = res.rc
        assert rc == 0


class TestAR004NoqaProtection:
    """Verify noqa directives suppress AR004 stripping."""

    def test_bare_noqa_on_def(self, tmp_path, reformat) -> None:
        src = """def outer():
    def _x():  # noqa
        pass
_x()
"""
        res = reformat.fix(src)
        after = res.after
        assert '_x' in after

    def test_noqa_on_call_site(self, tmp_path, reformat) -> None:
        src = """def outer():
    def _helper():
        pass
_helper()  # noqa: AR004
"""
        res = reformat.fix(src)
        after = res.after
        assert '_helper' in after


class TestAR004EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_func_preserved(self, tmp_path, reformat) -> None:
        src = """def outer():
    def __dunder():
        pass
__dunder()
"""  # dunder -> skipped by code
        after = reformat.fix(src).after
        assert '__dunder' in after

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        """Identifiers starting with __ are never stripped."""
        src = """def outer():
    def __inner():
        pass
__inner()
"""
        res = reformat.fix(src)
        after = res.after
        assert '__inner' in after

    def test_trailing_underscore_preserved(self, tmp_path, reformat) -> None:
        """Identifiers ending with underscore like 'cls_' stay."""
        src = """def outer():
    def cls_():
        pass
cls_()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'cls_' in after


class TestAR004AsyncFunctions:
    """Nested async functions should follow the same AR004 rules."""

    def test_async_nested_func_stripped(self, tmp_path, reformat) -> None:
        src = """def outer():
    async def _fetch():
        pass
    await _fetch()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'async def fetch()' in after


class TestAR004DeepNesting:
    """Test deeply nested functions."""

    def test_deeply_nested_stripped(self, tmp_path, reformat) -> None:
        src = """def outer():
    def middle():
        def _deep():
            pass
        _deep()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'def deep()' in after


class TestAR004MultipleNesting:
    """Test multiple nested functions at different levels."""

    def test_multiple_nested_stripped(self, tmp_path, reformat) -> None:
        src = """def outer():
    def _inner1():
        pass
    _inner1()

    class InnerClass:
        def method(self):
            def _inner2():
                pass
            _inner2()
"""
        res = reformat.fix(src)
        after = res.after
        assert 'def inner1()' in after
        assert 'def inner2()' in after
