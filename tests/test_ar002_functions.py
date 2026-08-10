"""Tests for AR002: Strip single leading underscores from top-level functions."""
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

class TestAR002FixMode:
    """In fix mode, AR002 strips underscore from top-level functions."""

    def test_strippable_func_is_renamed(self, tmp_path: Path) -> None:
        src = 'def _helper():\n\n    pass\n\n_helper()\n'
        _, after, _ = run_hook(tmp_path, src)
        assert 'def helper()' in after
        assert '_helper' not in after

    def test_unused_func_not_stripped(self, tmp_path: Path) -> None:
        """A function with no Load nodes for its name stays underscored."""
        src = 'def _orphan():\n\n    pass\n'
        _, after, _ = run_hook(tmp_path, src)
        assert '_orphan' in after

    def test_async_func_stripped_when_used(self, tmp_path: Path) -> None:
        src = 'async def _work():\n\n    pass\n\n_work()\n'
        _, after, rc = run_hook(tmp_path, src)
        assert 'async def work()' in after

    def test_clean_func_not_modified(self, tmp_path: Path) -> None:
        """Functions without leading underscore are untouched."""
        src = 'def helper():\n\n    pass\n'
        _, after, _ = run_hook(tmp_path, src)
        assert 'helper()' in after


# === Check Mode (non-fix) ===

class TestAR002CheckMode:
    """In check mode, AR002 reports violations without modifying files."""

    def test_violation_detected(self, tmp_path: Path) -> None:
        stdout, rc = run_check(tmp_path, 'def _x():\n\n    pass\n_x()\n')
        assert rc != 0
        assert 'AR002' in stdout

    def test_clean_file_no_violation(self, tmp_path: Path) -> None:
        stdout, rc = run_check(tmp_path, 'def x():\n\n    pass\nx()\n')
        assert rc == 0


# === Noqa Protection ===

class TestAR002NoqaProtection:
    """Verify noqa directives suppress AR002 stripping."""

    def test_bare_noqa_on_def(self, tmp_path: Path) -> None:
        src = 'def _x():\n\n    pass\n_x()  # noqa: AR002\n'
        _, after, _ = run_hook(tmp_path, src)
        assert '_x' in after

    def test_noqa_on_def_line(self, tmp_path: Path) -> None:
        """Noqa on the definition line protects."""
        run_check(tmp_path, '# noqa\n_x()\n')


# === Edge Cases ===

class TestAR002EdgeCases:
    """Names matching exclusion patterns must NOT be stripped."""

    def test_dunder_preserved(self, tmp_path: Path) -> None:
        src = 'def __version__():\n\n    pass\n'  # dunder -> skipped by code
        stdout, rc = run_check(tmp_path, src)
        assert '__version__' in src
        assert rc == 0

    def test_double_leading_underscore_preserved(self, tmp_path: Path) -> None:
        """Identifiers starting with __ are never stripped."""
        src = 'def __internal():\n\n    pass\n_x()\n'
        _, after, _ = run_hook(tmp_path, src)
        assert '__internal' in after

    def test_trailing_underscore_preserved(self, tmp_path: Path) -> None:
        """Identifiers ending with underscore like 'cls_' stay."""
        src = 'def cls_():\n\n    pass\ncls_()\n'
        _, after, _ = run_hook(tmp_path, src)
        assert 'cls_' in after


# === Async Functions ===

class TestAR002AsyncFunctions:
    """Top-level async functions should follow the same AR002 rules."""

    def test_async_func_with_underscore_stripped(self, tmp_path: Path) -> None:
        src = 'async def _fetch():\n\n    pass\n\n_fetch()\n'
        _, after, rc = run_hook(tmp_path, src)
        assert 'async def fetch()' in after
