"""Robustness tests: invalid / unparsable input must be a clean no-op.

The reformatter parses each file with ``ast``.  If the file cannot be parsed,
no rule may raise and no rule may rewrite the file: the tool should behave
exactly as if there were nothing to fix.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from hooks.agent_reformat import fix_blanks_ar013
from hooks.agent_reformat import run as run_hook

# Invalid Python: unclosed parenthesis plus other rule-triggering constructs.
INVALID_SOURCES = {
    'unclosed_paren': 'def foo(:\n    _x = 1\n    ##### sep #####\n    x = 1\n',
    'bad_indent': 'def foo():\npass\n',
    'stray_bracket': 'x = [1, 2,\n_y = 3\n',
    'unterminated_string': 'x = "abc\n_y = 1\n',
    'decorator_no_target': '@decorator\n',
}
ALL_CODES = [
    'AR001', 'AR002', 'AR003', 'AR004', 'AR005',
    'AR011', 'AR012', 'AR013', 'AR014',
    'AR021', 'AR022', 'AR031', 'AR032',
    'AR041', 'AR042', 'AR043', 'AR044', 'AR045',
]


def run_cli(path: Path, rules: str | None = None) -> int:
    """Run the CLI on *path*; return the exit code. Never raises SystemExit."""
    args = [str(path), '--fix']
    if rules:
        args.append(f'--rules={rules}')
    out, orig = io.StringIO(), sys.stdout
    rc = 0
    try:
        sys.stdout = out
        try:
            run_hook(args)
        except SystemExit as exc:
            rc = exc.code if exc.code is not None else 0
    finally:
        sys.stdout = orig
    return rc


@pytest.mark.parametrize('name', sorted(INVALID_SOURCES))
def test_invalid_file_left_unchanged_all_rules(tmp_path: Path, name: str) -> None:
    """A full default run must not crash or modify an unparsable file."""
    src = INVALID_SOURCES[name]
    f = tmp_path / 'bad.py'
    f.write_text(src)
    rc = run_cli(f)
    assert f.read_text() == src, f'{name}: invalid file was modified'
    assert rc == 0, f'{name}: expected success exit code, got {rc}'


@pytest.mark.parametrize('code', ALL_CODES)
def test_each_rule_noop_on_invalid_file(tmp_path: Path, code: str) -> None:
    """No individual rule may crash or rewrite an unparsable file."""
    src = INVALID_SOURCES['unclosed_paren']
    f = tmp_path / f'{code}.py'
    f.write_text(src)
    rc = run_cli(f, code)
    assert f.read_text() == src, f'{code}: modified an invalid file'
    assert rc == 0, f'{code}: expected success exit code, got {rc}'


@pytest.mark.parametrize('name', sorted(INVALID_SOURCES))
def test_check_mode_noop_on_invalid_file(tmp_path: Path, name: str) -> None:
    """Check mode (no --fix) must also survive invalid input."""
    src = INVALID_SOURCES[name]
    f = tmp_path / 'bad.py'
    f.write_text(src)
    out, orig = io.StringIO(), sys.stdout
    rc = 0
    try:
        sys.stdout = out
        try:
            run_hook([str(f), '--rules=AR013'])
        except SystemExit as exc:
            rc = exc.code if exc.code is not None else 0
    finally:
        sys.stdout = orig
    assert f.read_text() == src
    assert rc == 0, f'{name}: check mode rc={rc}'
    assert 'AR0' not in out.getvalue(), 'no violations should be reported'


def test_fix_blanks_ar013_returns_unchanged_on_invalid() -> None:
    """The AR013 helper must degrade to a no-op, not raise."""
    src = 'def foo(:\n    a = 1\n\n    b = 2\n'
    result, removed = fix_blanks_ar013(src, min_gap=3)
    assert result == src
    assert removed == set()


def test_valid_file_still_processed(tmp_path: Path) -> None:
    """Guard against the SyntaxError guard disabling valid processing."""
    valid = '_x = 1\nprint(_x)\n'
    f = tmp_path / 'good.py'
    f.write_text(valid)
    run_cli(f, 'AR001')
    assert f.read_text() == 'x = 1\nprint(x)\n'
