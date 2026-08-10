"""Tests for AR003: Strip single leading underscores from class methods."""
from __future__ import annotations

import io
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
# === Helpers ===


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str, int]:
    """Run agent-reformat in fix mode. Returns (pre, post, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(source_code)

    from hooks.agent_reformat import run

    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run([str(f), '--fix'])
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text(), rc


def run_check(tmp_path: Path, src: str) -> tuple[str, int]:
    """Run agent-reformat in check mode (no --fix). Returns (stdout, rc)."""
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

class TestAR003FixMode:
    """In fix mode AR003 strips underscore from class methods using a bare call."""

    def test_method_stripped_when_used(self, tmp_path: Path) -> None:
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
        _, after, rc = run_fix(tmp_path, src)
        assert 'def helper()' in after
        assert '_helper' not in after

    def test_unused_method_not_stripped(self, tmp_path: Path) -> None:
        """A method with no Load nodes for its name stays underscored."""
        src = (
            'class Foo:\n'
            '\n'
            '    def _orphan():\n'
            '\n'
            '        pass\n'  # no call -> not stripped
        )
        _, after, rc = run_fix(tmp_path, src)
        assert '_orphan' in after

    def test_clean_method_not_modified(self, tmp_path: Path) -> None:
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
        _, after, rc = run_fix(tmp_path, src)
        assert 'def helper()' in after


# === Check Mode (non-fix) ===

class TestAR003CheckMode:
    """In check mode AR003 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path: Path) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def _x():\n'
            '\n'
            '        pass\n'
            '\n'
            '_x()\n'
        )
        stdout, rc = run_check(tmp_path, src)
        assert rc != 0
        assert 'AR003' in stdout

    def test_clean_file_no_violation(self, tmp_path: Path) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def x():\n'
            '\n'
            '        pass\n'
            '\n'
            'x()\n'
        )
        stdout, rc = run_check(tmp_path, src)
        assert rc == 0


# === Noqa Protection ===

class TestAR003NoqaProtection:
    """Verify noqa directives suppress AR003 stripping."""

    def test_bare_noqa_on_def(self, tmp_path: Path) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def _x():  # noqa: AR003\n'
            '\n'
            '        pass\n'
            '\n'
            '_x()\n'
        )
        _, after, rc = run_fix(tmp_path, src)
        assert '_x' in after

    def test_noqa_on_call_site(self, tmp_path: Path) -> None:
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
        _, after, rc = run_fix(tmp_path, src)
        assert '_helper' in after


# === Edge Cases ===

class TestAR003EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_method_preserved(self, tmp_path: Path) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    def __init__():\n'
            '\n'
            '        pass\n'
        )  # dunder -> skipped by code logic
        _, after, rc = run_fix(tmp_path, src)
        assert '__init__' in after

    def test_double_leading_underscore_preserved(self, tmp_path: Path) -> None:
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
        _, after, rc = run_fix(tmp_path, src)
        assert '__helper' in after

    def test_trailing_underscore_preserved(self, tmp_path: Path) -> None:
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
        _, after, rc = run_fix(tmp_path, src)
        assert 'cls_' in after


# === Async Methods ===

class TestAR003AsyncMethods:
    """Async methods in classes should follow the same AR003 rules."""

    def test_async_method_stripped_when_used(self, tmp_path: Path) -> None:
        src = (
            'class Foo:\n'
            '\n'
            '    async def _fetch():\n'
            '\n'
            '        pass\n'
            '\n'
            '_fetch()\n'
        )
        _, after, rc = run_fix(tmp_path, src)
        assert 'async def fetch()' in after
