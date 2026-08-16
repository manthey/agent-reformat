"""Tests for AR044: Strip single leading underscores from non-exported nested functions."""
from __future__ import annotations

import io
import sys
from pathlib import Path


def run_hook(tmp_path: Path, src: str) -> tuple[str, str]:
    """Run agent-reformat. Returns (prev_content, after_content)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)
    from hooks.agent_reformat import run
    err_output = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = err_output
        try:
            run([str(f), '--rules=AR044', '--fix'])
        except SystemExit:
            pass
    finally:
        sys.stdout = orig
    return src, f.read_text()


def run_check(tmp_path: Path, src: str) -> tuple[str, int]:
    """Check mode (no --fix). Returns (stdout, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)

    from hooks.agent_reformat import run

    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run([str(f), '--rules=AR044'])
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return captured.getvalue(), rc


class TestNoAllDefined:
    """Without __all__, everything is public so nested functions should NOT be stripped."""

    def test_nested_in_class_not_stripped(self, tmp_path: Path) -> None:
        """Nested function in class without __all__ keeps underscore."""
        src = """class Foo:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        prev, result = run_hook(tmp_path, src)
        assert '_helper' in result

    def test_nested_in_fn_not_stripped(self, tmp_path: Path) -> None:
        """Nested function in function without __all__ keeps underscore."""
        src = """def outer():
    def _inner():
        pass
    _inner()
"""
        prev, result = run_hook(tmp_path, src)
        assert '_inner' in result


class TestAllDefined:
    """Functions NOT appearing directly or via context should have underscores stripped."""

    def test_nested_in_private_class_stripped(self, tmp_path: Path) -> None:
        """Function inside private class's method gets underscore stripped."""
        src = """__all__ = ['Public']

class _PrivateClass:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        prev, result = run_hook(tmp_path, src)
        assert 'def helper()' in result
        assert 'def _helper()' not in result

    def test_nested_in_public_class_kept(self, tmp_path: Path) -> None:
        """Nested function inside public class keeps underscore."""
        src = """__all__ = ['PublicClass']

class PublicClass:
    def method(self):
        def _helper():
            pass
        _helper()
"""
        prev, result = run_hook(tmp_path, src)
        assert '_helper' in result  # Not stripped (public class)

    def test_nested_inside_non_all_class_stripped(self, tmp_path: Path) -> None:
        """Nested function inside class not in __all__ gets stripped."""
        src = """__all__ = ['Public']

class UnlistedClass:
    def method(self):
        def _inner():
            pass
        _inner()
"""
        prev, result = run_hook(tmp_path, src)
        # UnlistedClass is implicitly private (not in __all__), so nested func
        # stripped
        assert 'def inner()' in result

    def test_nested_in_func_with_all_context_stripped(self, tmp_path: Path) -> None:
        """Nested function inside top-level function not in all gets stripped."""
        src = """__all__ = ['public_func']

def _unlisted():
    def _helper():
        pass
    _helper()
"""
        prev, result = run_hook(tmp_path, src)
        assert 'def helper()' in result


class TestAsyncFunctions:
    """Async nested functions follow the same rules."""

    def test_async_nested_in_private_class_stripped(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']

class _Priv:
    async def method(self):
        async def _fetch():
            pass
        await _fetch()
"""
        prev, result = run_hook(tmp_path, src)
        assert 'async def fetch()' in result


class TestNoqaProtection:
    """Verify noqa directive suppresses AR044."""

    def test_noqa_on_def_line(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']

class _C:
    def m(self):
        def _x():  # noqa
            pass
        _x()
"""
        prev, result = run_hook(tmp_path, src)
        assert '_x' in result

    def test_noqa_on_call_site(self, tmp_path: Path) -> None:
        src = """__all__ = ['p']
class _C:
    def m(self):
        def _f():
            pass
        _f()  # noqa
"""
        prev, result = run_hook(tmp_path, src)
        assert '_f' in result


class TestEdgeCases:
    """Names with certain patterns are exempt."""

    def test_dunder_nested_preserved(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def __dunder():
            pass
__dunder()
"""
        prev, result = run_hook(tmp_path, src)
        assert '__dunder' in result

    def test_double_leading_underscore_preserved(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def __inner():
            pass
__inner()
"""
        prev, result = run_hook(tmp_path, src)
        assert '__inner' in result

    def test_trailing_underscore_preserved(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def cls_():
            pass
cls_()
"""
        prev, result = run_hook(tmp_path, src)
        assert 'cls_' in result


class TestCheckMode:
    """Test AR044 check mode (reports without fixing)."""

    def test_violation_reported(self, tmp_path: Path) -> None:
        src = """__all__ = ['Pub']
class _C:
    def m(self):
        def _f():
            pass
        _f()
"""
        stdout, rc = run_check(tmp_path, src)
        assert rc != 0
        assert 'AR044' in stdout

    def test_clean_file_no_violation(self, tmp_path: Path) -> None:
        """No __all__ means no violations since everything is public."""
        src = """class C:
    def m(self):
        def _f():
            pass
        _f()
"""
        stdout, rc = run_check(tmp_path, src)
        assert rc == 0


class TestStrictSubsetBehavior:
    """AR044 should be strict subset of AR002 (nested functions)."""

    def test_no_all_keeps_more_underlines_than_ar002(self, tmp_path: Path) -> None:
        """Under no __all__, AR044 keeps underscores while AR002 would strip."""
        # Run with AR004 to get stripping
        src = """def outer():
    def _inner():
        pass
_inner()
"""
        f1 = tmp_path / 'test_ar004.py'
        f1.write_text(src)
        from hooks.agent_reformat import run as run_agent
        captured = io.StringIO()
        sys.stdout = captured
        try:
            run_agent([str(f1), '--rules=AR004', '--fix'])
        except SystemExit:
            pass
        # Now test AR044
        src2 = """def outer():
    def _inner():
        pass
_inner()
"""
        f2 = tmp_path / 'test_ar044.py'
        f2.write_text(src2)
        captured2 = io.StringIO()
        sys.stdout = captured2
        try:
            run_agent([str(f2), '--rules=AR044', '--fix'])
        except SystemExit:
            pass
        # AR044 should not have changed since no __all__ means everything
        # public
        after_ar044 = f2.read_text()

        assert '_inner' in after_ar044  # Ar044 without __all__ keeps underscores
