"""Tests for AR021 (repeating comment chars) and AR022 (long comment lines).

AR021: Remove comment-only lines with 4+ identical non-whitespace chars.
AR022: Flag comment-only lines exceeding max line length (error only, no fix).
"""
from __future__ import annotations


class TestAR021RepeatingComments:
    """Lines containing only a comment with 4+ identical non-whitespace chars."""

    def test_repeated_hash_removed(self, tmp_path, reformat) -> None:
        """A line of repeated hashes (50 #'s) should be removed."""
        src = '##############################\nprint("x")\ny=1\nz=2\n'
        after = reformat.fix(src, 'AR021').after
        # The long hash line should have been removed
        assert '##############################' not in after
        assert after == 'print("x")\ny=1\nz=2\n'

    def test_four_char_minimum_threshold(self, tmp_path, reformat) -> None:
        """Exactly 4 repeated chars should be removed (threshold)."""
        src = '####\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        assert '####' not in after
        assert after == 'x = 1\n'

    def test_three_char_not_removed(self, tmp_path, reformat) -> None:
        """Exactly 3 repeated chars should NOT be removed."""
        src = '###\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        assert after == src

    def test_normal_comment_kept(self, tmp_path, reformat) -> None:
        """Normal single-line comment should be preserved."""
        src = '# This is a normal comment\nx = 1\ny = 2\n'
        after = reformat.fix(src, 'AR021').after
        assert '# This is a normal comment' in after
        assert after == src

    def test_separate_comment_lines_removed(self, tmp_path, reformat) -> None:
        """Multiple repeated-char comment lines should all be removed."""
        src = '# header\n########\nx = 1\n--------\ny = 2\nz = 3\n'
        after = reformat.fix(src, 'AR021').after
        assert '########' not in after
        # The all-dahes line is NOT a comment line (no leading #),
        # it's parsed as an expression statement by Python
        assert '--------' in after

    def test_repeated_hash_separators_removed(self, tmp_path, reformat) -> None:
        """Lines of repeated hash comment separators should be removed."""
        src = 'x = 1\n###########\ny = 2\n###########\nz = 3\n'
        after = reformat.fix(src, 'AR021').after
        assert '###########' not in after
        assert after == 'x = 1\ny = 2\nz = 3\n'

    def test_noqa_line_removed_as_repeated_char(self, tmp_path, reformat) -> None:
        """Line with only ## noqa is still a repeated-char comment and gets removed."""
        src = '# ##\n#############\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        # The line with just ## (2 #'s) followed by space and text has
        # different chars. Only the 13 #'s on its own line should be removed
        assert '#############' not in after

    def test_repeated_dash_comment_removed(self, tmp_path, reformat) -> None:
        """A line of repeated dashes as a comment should be removed."""
        src = '# --------\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        assert after == 'x = 1\n'

    def test_repeated_underscore_comment_removed(self, tmp_path, reformat) -> None:
        """A line of repeated underscores as a comment should be removed."""
        src = '# ________\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        assert '# ________' not in after
        assert after == 'x = 1\n'

    def test_repeated_at_comment_removed(self, tmp_path, reformat) -> None:
        """A line of repeated @ as a comment should be removed."""
        src = '# @@@@@@@@\nx = 1\n'
        after = reformat.fix(src, 'AR021').after
        assert '# @@@@@@@@' not in after
        assert after == 'x = 1\n'

    def test_comment_between_code_removed(self, tmp_path, reformat) -> None:
        """Repeated-char comment line between code lines should be removed."""
        src = 'def foo():\n    pass\n##########\nfoo()\n'
        after = reformat.fix(src, 'AR021').after
        assert '##########' not in after


class TestAR022CommentLength:
    """Long comment-only lines produce violations in check mode."""

    def test_check_mode_with_long_comment(self, tmp_path, reformat) -> None:
        """A comment-only line exceeding 79 chars should return exit code 1."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        res = reformat.check(src, 'AR022')
        output, rc = res.stdout, res.rc
        # Line is: "# " + 78 chars = 80 chars total, which exceeds 79
        assert rc == 1, f'Expected error exit code 1, got {rc}. output: {output}'
        assert 'AR022' in output, f'Expected AR022 violation in output. Got: {output}'
        # Check for new format with length info
        assert '80>79' in output, f'Expected length info in output. Got: {output}'

    def test_long_comment_exactly_at_threshold(self, tmp_path, reformat) -> None:
        """A comment-only line exactly 79 chars should NOT be flagged."""
        src = 'x=1\n# ' + 'a' * 77 + '\ny=2\nz=3\n'
        res = reformat.check(src, 'AR022')
        output, rc = res.stdout, res.rc
        assert rc == 0, f'Expected clean exit code 0, got {rc}. output: {output}'

    def test_long_comment_80_chars_flagged(self, tmp_path, reformat) -> None:
        """A comment-only line of exactly 80 chars should be flagged."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        res = reformat.check(src, 'AR022')
        output, rc = res.stdout, res.rc
        assert rc == 1
        assert '80>79' in output

    def test_short_comment_does_not_flag(self, tmp_path, reformat) -> None:
        """Short comment-only lines should not be flagged."""
        src = 'x=1\n# ok short comment\ny=2\nz=3\n'
        res = reformat.check(src, 'AR022')
        rc = res.rc
        assert rc == 0

    def test_inline_comment_ignored_by_ar022(self, tmp_path, reformat) -> None:
        """AR022 should only flag comment-only lines, not inline comments."""
        src = ('x = 1  # This is a very long inline comment that goes on and '
               'on and on and on\ny = 2\n')
        res = reformat.check(src, 'AR022')
        rc = res.rc
        assert rc == 0

    def test_check_mode_no_file_change(self, tmp_path, reformat) -> None:
        """AR022 check mode should not modify the file."""
        src = 'x=1\n# ' + 'a' * 78 + '\ny=2\nz=3\n'
        result = reformat.check(src, 'AR022')
        assert result.after == src

    def test_multiple_long_comments_reported(self, tmp_path, reformat) -> None:
        """Multiple long comment lines should all be reported."""
        src = '# ' + 'b' * 78 + '\n# ' + 'c' * 78 + '\n'
        res = reformat.check(src, 'AR022')
        output, rc = res.stdout, res.rc
        assert rc == 1
        assert output.count('AR022') >= 2
        # Each should have length info
        assert output.count('80>79') >= 2
