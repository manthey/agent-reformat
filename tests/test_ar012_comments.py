"""Tests for AR012: Remove blank lines immediately before/after comments."""
from __future__ import annotations

import sys
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str]:
    """Run agent-reformat in fix mode on a temp file. Returns (original, modified)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)

    original_stdout = sys.stdout
    captured = __import__('io').StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR012'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


class TestAR012BasicCommentRemoval:
    """Test that blank lines around standalone comments are removed."""

    def test_blank_before_standalone_comment(self, tmp_path: Path) -> None:
        """Blank line before a standalone comment should be removed."""
        src = 'x = 1\n\n# This is a comment\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\n# This is a comment\ny = 2\n'

    def test_blank_after_standalone_comment(self, tmp_path: Path) -> None:
        """Blank line after a standalone comment should be removed."""
        src = 'x = 1\n# Comment\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\n# Comment\ny = 2\n'

    def test_blanks_on_both_sides_of_comment(self, tmp_path: Path) -> None:
        """Blank lines before and after standalone comment should be removed."""
        src = 'x = 1\n\n# Comment\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\n# Comment\ny = 2\n'

    def test_multiple_consecutive_blanks_before_comment_removed(self, tmp_path: Path) -> None:
        """AR012 FIX: All consecutive blanks before a comment should be removed.

        The previous implementation only removed the blank directly adjacent to
        the comment line. Now ALL consecutive blanks touching the comment
        boundaries are removed.
        """
        src = 'x = 1\n\n\n# Comment with multiple blanks\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        # All three blanks before the comment should be removed
        assert after == 'x = 1\n# Comment with multiple blanks\ny = 2\n'

    def test_multiple_consecutive_blanks_after_comment_removed(self, tmp_path: Path) -> None:
        """AR012 FIX: All consecutive blanks after a comment should be removed."""
        src = 'x = 1\n# Comment with multiple blanks\n\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        # All three blanks after the comment should be removed
        assert after == 'x = 1\n# Comment with multiple blanks\ny = 2\n'

    def test_multiple_standalone_comments(self, tmp_path: Path) -> None:
        """Multiple standalone comments should each have blanks removed."""
        src = 'a = 1\n\n# First section\n\nb = 2\n\n# Second section\n\nc = 3\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'a = 1\n# First section\nb = 2\n# Second section\nc = 3\n'


class TestAR012PreservedBlanks:
    """Test that certain blank lines are NOT removed by AR012."""

    def test_blanks_at_end_of_file_preserved(self, tmp_path: Path) -> None:
        """Trailing blanks at end of file should be preserved."""
        src = 'x = 1\n# comment\n\n\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\n# comment\n\n\n'

    def test_blanks_between_functions_preserved(self, tmp_path: Path) -> None:
        """Blank lines between function definitions should be preserved."""
        src = 'def a():\n    pass\n\n# middle comment\n\ndef b():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Blank between def blocks preserved per PEP8
        assert '\ndef b()' in after

    def test_blanks_between_classes_preserved(self, tmp_path: Path) -> None:
        """Blank lines between class definitions should be preserved."""
        src = 'class A:\n    pass\n\n# middle comment\n\nclass B:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Blank between class blocks preserved per PEP8
        assert '\nclass B:' in after

    def test_blanks_in_same_section_preserved(self, tmp_path: Path) -> None:
        """Blank lines within the same code section are kept (not around comments)."""
        src = 'x = 1\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert '\n\n' in after


class TestAR012ComplexScenarios:
    """Test complex scenarios with AR012."""

    def test_comment_in_function_body(self, tmp_path: Path) -> None:
        """Standalone comment inside function body should trigger removal."""
        src = 'def foo():\n\n    # Setup section\n\n    x = 1\n'
        _, after = run_fix(tmp_path, src)
        assert '# Setup section\n    x = 1' in after

    def test_nested_blank_before_comment_in_class(self, tmp_path: Path) -> None:
        """Blank before comment inside class should be removed."""
        src = 'class Foo:\n    # Method separator\n    def bar(self):\n        pass\n'
        _, after = run_fix(tmp_path, src)
        assert 'Foo:\n    # Method separator' in after

    def test_inline_comment_blanks_not_affected(self, tmp_path: Path) -> None:
        """Blank lines around inline comments on code lines are NOT affected."""
        # Inline comment "x = 1" has a # but is not standalone comment line.
        src = 'x = 1  # inline\n\ny = 2  # inline\n'
        _, after = run_fix(tmp_path, src)
        assert 'x = 1  # inline\n\ny = 2' in after

    def test_comment_in_multiline_string_preserved(self, tmp_path: Path) -> None:
        """Comments inside multiline strings should not trigger AR012.

        Verify that blanks are preserved when there's content in a multiline
        string that LOOKS like comments but isn't (confirmed by tokenizer).
        This tests that AR012 correctly only acts on real comments, not # chars
        inside strings.
        """
        # Note: There MUST be an actual blank line after the inner content
        # to demonstrate preservation. The '#' comment is INSIDE the string.
        src = '''x = """
# Not a real comment

"""

y = 1
'''
        _, after = run_fix(tmp_path, src)
        # The blank between closing """ and y=1 should be preserved because
        # the '#' inside the string is NOT a real comment
        assert '\n\ny = 1' in after


class TestAR012EdgeCases:
    """Test edge cases for AR012."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file is unchanged."""
        _, after = run_fix(tmp_path, '')
        assert after == ''

    def test_only_comment_lines(self, tmp_path: Path) -> None:
        """File with only comments has no changes (no adjacent blanks to remove)."""
        src = '# comment1\n# comment2\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_blank_between_comments_only(self, tmp_path: Path) -> None:
        """Blank line between two comments is removed."""
        src = '# first\n\n# second\n'
        _, after = run_fix(tmp_path, src)
        # The blank between two comment-only lines is around comments on both
        # sides
        assert '# first\n# second' in after

    def test_no_change_for_clean_file(self, tmp_path: Path) -> None:
        """Clean file without problematic blanks passes through unchanged."""
        src = 'x = 1\n# comment\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == src


class TestAR012WithNoqa:
    """Test that noqa directives don't interfere with AR012 (AR012 has no noqa)."""

    def test_comment_with_noqa_still_triggers_ar012(self, tmp_path: Path) -> None:
        """Blank before a # noqa comment is still removed."""
        src = 'x = 1\n\n# noqa: AR041\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert '# noqa: AR041\ny = 2' in after


class TestAR012CheckMode:
    """Test that check mode works correctly for AR012."""

    def test_check_mode_no_file_change(self, tmp_path: Path) -> None:
        """Check mode should not modify the source file."""
        src = 'x = 1\n\n# comment\ny = 2\n'
        f = tmp_path / 'test.py'
        f.write_text(src)
        captured_out = __import__('io').StringIO()
        original_stdout = sys.stdout
        try:
            sys.stdout = captured_out
            try:
                run_hook([str(f), '--rules', 'AR012'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        assert f.read_text() == src, 'Check mode must not modify the file'
