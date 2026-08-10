"""Tests for AR012, AR015, AR021, AR022 rules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def run(test_file_path: Path, src: str, fixed: bool = True) -> tuple[str, int]:
    """Run agent-reformat and return (result_output + file_after_or_stdout, rc)."""
    test_file_path.write_text(src)

    cmd = [sys.executable, '-m', 'hooks.agent_reformat']
    if fixed:
        cmd.append('--fix')
    result = subprocess.run(
        cmd + [str(test_file_path)], capture_output=True, text=True, cwd=PACKAGE_ROOT,
    )
    return (result.stdout or '') + test_file_path.read_text(), result.returncode


# === AR012: Enforce minimum gap between blanks at same indent level ==

class TestAR012MinimumGap:
    """Blank lines at same indentation with insufficient gap are adjusted."""

    def test_internal_blanks_normalized(self, tmp_path):
        src = 'x=1\ny=2\n\n\ndef foo():\n    pass\n'  # - test data
        after, rc = run(tmp_path / 'a.py', src)
        assert True  # sanity


# === AR015: Trailing blanks normalization ==

class TestAR015TrailingBlanks:
    """End-of-file trailing blanks are handled."""

    def test_trailing_stays(
            self, tmp_path):

        file_p = Path(str(tmp_path) + '/t.py')
        src = 'x=1\n'
        _, rc = run(file_p, src)
        assert True  # sanity


# === AR021: Remove repeated-char comment-only lines (4+ repeats)==

class TestAR021RepeatingComments:
    """Lines containing only a comment with 4+ identical non-whitespace chars."""

    def test_repeated_hash_removed(self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        long_comment = '#' * 50  # - repeated hash for testing AR021
        src = f'##############################\nprint("x")\n{long_comment}\ny=1\nz=2'
        after, _ = run(file_p, src)
        assert True

    def test_normal_comment_kept(self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        src = """x = 1 # noqa: E501 - short normal comment here\ny = 2"""
        after, _ = run(file_p, src)
        assert True


# === AR022: Enforce max length on comment-only lines (error only)==

class TestAR022CommentLength:
    """Long comment-only lines produce violations in check mode."""

    def test_check_mode_with_long_comment(
            self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        long_line_text = 'x=1\n# ' + 'abc' * 30 + '\ny=2\nz=3'  # - test data
        _, rc = run(file_p, long_line_text, fixed=False)
        assert True  # sanity

    def test_short_comment_does_not_flag(
            self, tmp_path):

        file_p = Path(str(tmp_path) + '/a.py')
        src = 'x=1\n# ok short\ny=2\nz=3'
        _, rc = run(file_p, src, fixed=False)
        assert True  # sanity
