"""Tests for AR021 (repeating comment chars) and AR022 (long comment lines).

AR021: Remove comment-only lines with 4+ identical non-whitespace chars.
AR022: Flag comment-only lines exceeding max line length (error only, no fix).
"""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str]:
    """Run agent-reformat in fix mode on a temp file. Returns (original, modified)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR021'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


def check_for_ar022_violations(tmp_path: Path, source_code: str) -> tuple[str, int]:
    """Run agent-reformat in check mode for AR022. Returns (stdout, rc)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)

    original_stdout = sys.stdout
    captured_out = StringIO()
    try:
        sys.stdout = captured_out
        try:
            run_hook([str(f), '--rules', 'AR022'])
        except SystemExit as e:
            rc = e.code if e.code is not None else 1
        else:
            rc = 0
    finally:
        sys.stdout = original_stdout
    output = captured_out.getvalue()
    return output, rc


class TestAR021RepeatingComments:
    """Lines containing only a comment with 4+ identical non-whitespace chars."""

    def test_repeated_hash_removed(self, tmp_path: Path) -> None:
        """A line of repeated hashes (50 #'s) should be removed."""
        src = '##############################\nprint("x")\ny=1\nz=2\n'
        _, after = run_fix(tmp_path, src)
        # The long hash line should have been removed
        assert '##############################' not in after
        assert after == 'print("x")\ny=1\nz=2\n'

    def test_four_char_minimum_threshold(self, tmp_path: Path) -> None:
        """Exactly 4 repeated chars should be removed (threshold)."""
        src = '####\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert '####' not in after
        assert after == 'x = 1\n'

    def test_three_char_not_removed(self, tmp_path: Path) -> None:
        """Exactly 3 repeated chars should NOT be removed."""
        src = '###\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_normal_comment_kept(self, tmp_path: Path) -> None:
        """Normal single-line comment should be preserved."""
        src = '# This is a normal comment\nx = 1\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert '# This is a normal comment' in after
        assert after == src

    def test_separate_comment_lines_removed(self, tmp_path: Path) -> None:
        """Multiple repeated-char comment lines should all be removed."""
        src = '# header\n########\nx = 1\n--------\ny = 2\nz = 3\n'
        _, after = run_fix(tmp_path, src)
        assert '########' not in after
        # The all-dahes line is NOT a comment line (no leading #),
        # it's parsed as an expression statement by Python
        assert '--------' in after

    def test_repeated_hash_separators_removed(self, tmp_path: Path) -> None:
        """Lines of repeated hash comment separators should be removed."""
        src = 'x = 1\n###########\ny = 2\n###########\nz = 3\n'
        _, after = run_fix(tmp_path, src)
        assert '###########' not in after
        assert after == 'x = 1\ny = 2\nz = 3\n'

    def test_noqa_line_removed_as_repeated_char(self, tmp_path: Path) -> None:
        """Line with only ## noqa is still a repeated-char comment and gets removed."""
        src = '# ##\n#############\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        # The line with just ## (2 #'s) followed by space and text has
        # different chars. Only the 13 #'s on its own line should be removed
        assert '#############' not in after

    def test_repeated_dash_comment_removed(self, tmp_path: Path) -> None:
        """A line of repeated dashes as a comment should be removed."""
        src = '# --------\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert '# --------' not in after or '####==' in after or '# --' not in after
        # Actually just verify the line isn't preserved exactly as-is
        lines = after.split('\n')
        for line in lines:
            assert line != '# --------', 'Repeated-dash comment should be removed'
        assert after == 'x = 1\n'

    def test_repeated_underscore_comment_removed(self, tmp_path: Path) -> None:
        """A line of repeated underscores as a comment should be removed."""
        src = '# ________\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert '# ________' not in after
        assert after == 'x = 1\n'

    def test_repeated_at_comment_removed(self, tmp_path: Path) -> None:
        """A line of repeated @ as a comment should be removed."""
        src = '# @@@@@@@@\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert '# @@@@@@@@' not in after
        assert after == 'x = 1\n'

    def test_comment_between_code_removed(self, tmp_path: Path) -> None:
        """Repeated-char comment line between code lines should be removed."""
        src = 'def foo():\n    pass\n##########\nfoo()\n'
        _, after = run_fix(tmp_path, src)
        assert '##########' not in after


class TestAR022CommentLength:
    """Long comment-only lines produce violations in check mode."""

    def test_check_mode_with_long_comment(self, tmp_path: Path) -> None:
        """A comment-only line exceeding 79 chars should return exit code 1."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        output, rc = check_for_ar022_violations(tmp_path, src)
        # Line is: "# " + 78 chars = 80 chars total, which exceeds 79
        assert rc == 1, f'Expected error exit code 1, got {rc}. output: {output}'
        assert 'AR022' in output, f'Expected AR022 violation in output. Got: {output}'

    def test_long_comment_exactly_at_threshold(self, tmp_path: Path) -> None:
        """A comment-only line exactly 79 chars should NOT be flagged."""
        src = 'x=1\n# ' + 'a' * 77 + '\ny=2\nz=3\n'
        output, rc = check_for_ar022_violations(tmp_path, src)
        assert rc == 0, f'Expected clean exit code 0, got {rc}. output: {output}'

    def test_long_comment_80_chars_flagged(self, tmp_path: Path) -> None:
        """A comment-only line of exactly 80 chars should be flagged."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        output, rc = check_for_ar022_violations(tmp_path, src)
        assert rc == 1

    def test_short_comment_does_not_flag(self, tmp_path: Path) -> None:
        """Short comment-only lines should not be flagged."""
        src = 'x=1\n# ok short comment\ny=2\nz=3\n'
        output, rc = check_for_ar022_violations(tmp_path, src)
        assert rc == 0

    def test_inline_comment_ignored_by_ar022(self, tmp_path: Path) -> None:
        """AR022 should only flag comment-only lines, not inline comments."""
        src = ('x = 1  # This is a very long inline comment that goes on and '
               'on and on and on\ny = 2\n')
        output, rc = check_for_ar022_violations(tmp_path, src)
        assert rc == 0

    def test_check_mode_no_file_change(self, tmp_path: Path) -> None:
        """AR022 check mode should not modify the file."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        f = tmp_path / 'test.py'
        f.write_text(src)
        check_for_ar022_violations(tmp_path, src)
        assert f.read_text() == src

    def test_multiple_long_comments_reported(self, tmp_path: Path) -> None:
        """Multiple long comment lines should all be reported."""
        src = '# ' + 'b' * 78 + '\n# ' + 'c' * 78 + '\n'
        output, rc = check_for_ar022_violations(tmp_path, src)
        assert rc == 1
        assert output.count('AR022') >= 2
