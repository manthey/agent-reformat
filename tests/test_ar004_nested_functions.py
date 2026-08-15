"""Tests for AR004: Strip single leading underscores from nested functions."""
from __future__ import annotations

import io
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def run_hook(tmp_path: Path, source_code: str, fix: bool = True) -> tuple[str, str, int]:
    """Run agent-reformat on a temp file. Returns (pre, post, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(source_code)

    from hooks.agent_reformat import run

    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            cmd_args = [str(f), '--fix'] if fix else [str(f)]
            run(cmd_args)
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text(), rc


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
            run([str(f)])
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return captured.getvalue(), rc


# === Fix Mode ===


class TestAR004FixMode:
    """In fix mode, AR004 strips underscore from nested functions."""

    def test_nested_func_in_top_level_fn_stripped(self, tmp_path: Path) -> None:
        """Nested function inside top-level function has underscore stripped."""
        src = '''def outer():
    def _inner():
        pass
    _inner()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'def inner()' in after
        assert '_inner' not in after

    def test_nested_func_in_class_method_stripped(self, tmp_path: Path) -> None:
        """Nested function inside class method has underscore stripped."""
        src = '''class Foo:
    def method(self):
        def _inner():
            pass
        _inner()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'def inner()' in after
        assert '_inner' not in after

    def test_unused_nested_func_not_stripped(self, tmp_path: Path) -> None:
        """Unused nested function is NOT stripped (no Load nodes)."""
        src = '''def outer():
    def _orphan():
        pass
'''
        _, after, rc = run_hook(tmp_path, src)
        assert '_orphan' in after

    def test_clean_nested_func_not_modified(self, tmp_path: Path) -> None:
        """Nested function without underscore is untouched."""
        src = '''def outer():
    def inner():
        pass
    inner()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'def inner()' in after


# === Check Mode (non-fix) ===


class TestAR004CheckMode:
    """In check mode, AR004 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path: Path) -> None:
        src = '''def outer():
    def _x():
        pass
_x()
'''
        stdout, rc = run_check(tmp_path, src)
        assert rc != 0
        assert 'AR004' in stdout

    def test_clean_file_no_violation(self, tmp_path: Path) -> None:
        src = '''def outer():
    def x():
        pass
x()
'''
        stdout, rc = run_check(tmp_path, src)
        assert rc == 0


# === Noqa Protection ===


class TestAR004NoqaProtection:
    """Verify noqa directives suppress AR004 stripping."""

    def test_bare_noqa_on_def(self, tmp_path: Path) -> None:
        src = '''def outer():
    def _x():  # noqa
        pass
_x()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert '_x' in after

    def test_noqa_on_call_site(self, tmp_path: Path) -> None:
        src = '''def outer():
    def _helper():
        pass
_helper()  # noqa: AR004
'''
        _, after, rc = run_hook(tmp_path, src)
        assert '_helper' in after


# === Edge Cases ===


class TestAR004EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_func_preserved(self, tmp_path: Path) -> None:
        src = '''def outer():
    def __dunder():
        pass
__dunder()
'''  # dunder -> skipped by code
        _, rc = run_check(tmp_path, src)
        assert '__dunder' in src

    def test_double_leading_underscore_preserved(self, tmp_path: Path) -> None:
        """Identifiers starting with __ are never stripped."""
        src = '''def outer():
    def __inner():
        pass
__inner()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert '__inner' in after

    def test_trailing_underscore_preserved(self, tmp_path: Path) -> None:
        """Identifiers ending with underscore like 'cls_' stay."""
        src = '''def outer():
    def cls_():
        pass
cls_()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'cls_' in after


# === Async Functions ===


class TestAR004AsyncFunctions:
    """Nested async functions should follow the same AR004 rules."""

    def test_async_nested_func_stripped(self, tmp_path: Path) -> None:
        src = '''def outer():
    async def _fetch():
        pass
    await _fetch()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'async def fetch()' in after


# === Deeply Nested Functions ===


class TestAR004DeepNesting:
    """Test deeply nested functions."""

    def test_deeply_nested_stripped(self, tmp_path: Path) -> None:
        src = '''def outer():
    def middle():
        def _deep():
            pass
        _deep()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'def deep()' in after


class TestAR004MultipleNesting:
    """Test multiple nested functions at different levels."""

    def test_multiple_nested_stripped(self, tmp_path: Path) -> None:
        src = '''def outer():
    def _inner1():
        pass
    _inner1()
    
    class InnerClass:
        def method(self):
            def _inner2():
                pass
            _inner2()
'''
        _, after, rc = run_hook(tmp_path, src)
        assert 'def inner1()' in after
        assert 'def inner2()' in after
