"""Tests for AR044: Strip single leading underscores from non-exported nested functions."""
from __future__ import annotations


class TestNoAllDefined:
    """Without __all__, everything is public so nested functions should NOT be stripped."""

    def test_nested_in_class_not_stripped(self, tmp_path, reformat) -> None:
        """Nested function in class without __all__ keeps underscore."""
        src = """class Foo:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        result = reformat.fix(src, 'AR044').after
        assert '_helper' in result

    def test_nested_in_fn_not_stripped(self, tmp_path, reformat) -> None:
        """Nested function in function without __all__ keeps underscore."""
        src = """def outer():
    def _inner():
        pass
    _inner()
"""
        result = reformat.fix(src, 'AR044').after
        assert '_inner' in result


class TestAllDefined:
    """Functions NOT appearing directly or via context should have underscores stripped."""

    def test_nested_in_private_class_stripped(self, tmp_path, reformat) -> None:
        """Function inside private class's method gets underscore stripped."""
        src = """__all__ = ['Public']

class _PrivateClass:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        result = reformat.fix(src, 'AR044').after
        assert 'def helper()' in result
        assert 'def _helper()' not in result

    def test_nested_in_public_class_kept(self, tmp_path, reformat) -> None:
        """Nested function inside public class keeps underscore."""
        src = """__all__ = ['PublicClass']

class PublicClass:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        result = reformat.fix(src, 'AR044').after
        assert '_helper' in result  # Not stripped (public class)

    def test_nested_inside_non_all_class_stripped(self, tmp_path, reformat) -> None:
        """Nested function inside class not in __all__ gets stripped."""
        src = """__all__ = ['Public']

class UnlistedClass:
    def method(self):
        def _inner():
            pass
        _inner()
"""
        result = reformat.fix(src, 'AR044').after
        # UnlistedClass is implicitly private (not in __all__), so nested func
        # stripped
        assert 'def inner()' in result

    def test_nested_in_func_with_all_context_stripped(self, tmp_path, reformat) -> None:
        """Nested function inside top-level function not in all gets stripped."""
        src = """__all__ = ['public_func']

def _unlisted():
    def _helper():
        pass
    _helper()
"""
        result = reformat.fix(src, 'AR044').after
        assert 'def helper()' in result


class TestAsyncFunctions:
    """Async nested functions follow the same rules."""

    def test_async_nested_in_private_class_stripped(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']

class _Priv:
    async def method(self):
        async def _fetch():
            pass
        await _fetch()
"""
        result = reformat.fix(src, 'AR044').after
        assert 'async def fetch()' in result


class TestNoqaProtection:
    """Verify noqa directive suppresses AR044."""

    def test_noqa_on_def_line(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']

class _C:
    def m(self):
        def _x():  # noqa
            pass
        _x()
"""
        result = reformat.fix(src, 'AR044').after
        assert '_x' in result

    def test_noqa_on_call_site(self, tmp_path, reformat) -> None:
        src = """__all__ = ['p']
class _C:
    def m(self):
        def _f():
            pass
        _f()  # noqa
"""
        result = reformat.fix(src, 'AR044').after
        assert '_f' in result


class TestEdgeCases:
    """Names with certain patterns are exempt."""

    def test_dunder_nested_preserved(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def __dunder():
            pass
__dunder()
"""
        result = reformat.fix(src, 'AR044').after
        assert '__dunder' in result

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def __inner():
            pass
__inner()
"""
        result = reformat.fix(src, 'AR044').after
        assert '__inner' in result

    def test_trailing_underscore_preserved(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def cls_():
            pass
cls_()
"""
        result = reformat.fix(src, 'AR044').after
        assert 'cls_' in result


class TestCheckMode:
    """Test AR044 check mode (reports without fixing)."""

    def test_violation_reported(self, tmp_path, reformat) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def _f():
            pass
        _f()
"""
        res = reformat.check(src, 'AR044')
        stdout, rc = res.stdout, res.rc
        assert rc != 0
        assert 'AR044' in stdout

    def test_clean_file_no_violation(self, tmp_path, reformat) -> None:
        """No __all__ means no violations since everything is public."""
        src = """class C:
    def m(self):
        def _f():
            pass
        _f()
"""
        res = reformat.check(src, 'AR044')
        rc = res.rc
        assert rc == 0


class TestStrictSubsetBehavior:
    """AR044 should be strict subset of AR002 (nested functions)."""

    def test_no_all_keeps_more_underlines_than_ar002(self, reformat) -> None:
        """Under no __all__, AR044 keeps underscores while AR002 would strip."""
        src = """def outer():
    def _inner():
        pass
_inner()
"""
        # AR004 strips regardless of export status.
        ar004_after = reformat.fix(src, 'AR004', filename='test_ar004.py').after
        assert '_inner' not in ar004_after
        # AR044 leaves it alone: no __all__ means everything is public.
        after = reformat.fix(src, 'AR044', filename='test_ar044.py').after
        assert '_inner' in after  # AR044 without __all__ keeps underscores
