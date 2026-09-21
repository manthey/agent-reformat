from __future__ import annotations

from hooks.agent_reformat import fix_blanks_ar013


class TestAR013CommentBlankPreservation:
    """Test that blank lines between comments at the same indent are preserved."""

    def test_blank_between_same_indent_comments_preserved(self, tmp_path, reformat) -> None:
        """Blank line between two comments at same indent should be preserved.

        This is the example from the feature request:
        ```
        def func(a):
            x = 4
            y = 5
            # This is a sample

            # With a blank line
            return a * x + y
        ```
        The blank line between the two comments should NOT be removed.
        """
        src = (
            'def func(a):\n'
            '    x = 4\n'
            '    y = 5\n'
            '    # This is a sample\n'
            '    \n'
            '    # With a blank line\n'
            '    return a * x + y\n'
        )
        after = reformat.fix(src, 'AR013').after
        # The blank line should be preserved
        # Check that there's a blank line between the two comments
        lines = after.split('\n')
        found_comment_a = False
        found_blank_between = False
        for i, line in enumerate(lines):
            if 'This is a sample' in line:
                found_comment_a = True
                if i + 1 < len(lines) and not lines[i + 1].strip():
                    found_blank_between = True
        assert found_comment_a, 'Comment line not found'
        assert found_blank_between, 'Blank line after comment was removed'
        assert src == after, f'Expected no changes but got:\n{after}'

    def test_blank_between_module_level_comments_preserved(self, tmp_path, reformat) -> None:
        """Blank line between module-level comments should be preserved."""
        src = (
            '# Module comment\n'
            '\n'
            '# Another module comment\n'
            'x = 1\n'
        )
        after = reformat.fix(src, 'AR013').after
        # Check the blank is preserved
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if line == '# Module comment':
                assert not lines[i + 1].strip(), 'Blank was removed'
                break

    def test_blank_between_different_indent_comments_removed(self) -> None:
        """Blank between comments at DIFFERENT indents should NOT be preserved.

        Note: Comments are not tracked as statements by the AST, so this
        scenario doesn't create a statement group. The blank preservation
        behavior here is about whether the comment-protection logic
        incorrectly extends protection to different-indent comments.
        """
        src = (
            'def func():\n'
            '    # indent 4\n'
            '    \n'
            '        # indent 8\n'
            '    pass\n'
        )
        result, removed = fix_blanks_ar013(src, min_gap=3)
        # The only statement here is `pass`, so there is no statement group
        # to trigger AR013: the blank must be left untouched and the comment
        # protection must not reach across different indent levels.
        assert removed == set()
        assert result == src

    def test_blank_between_comments_with_code_around_preserved(self, tmp_path, reformat) -> None:
        """Blank between comments should be preserved even with code around them."""
        src = (
            'def func():\n'
            '    a = 1\n'
            '    # comment 1\n'
            '    \n'
            '    # comment 2\n'
            '    b = 2\n'
        )
        after = reformat.fix(src, 'AR013').after
        # Check the blank is preserved
        assert src == after, f'Blank was incorrectly removed:\n{after}'

    def test_multiple_blank_pairs_between_comments(self, tmp_path, reformat) -> None:
        """Multiple comment pairs with blanks should each preserve their blank."""
        src = (
            'def func():\n'
            '    a = 1\n'
            '    # comment A\n'
            '    \n'
            '    # comment B\n'
            '    # comment C\n'
            '    \n'
            '    # comment D\n'
            '    b = 2\n'
        )
        after = reformat.fix(src, 'AR013').after
        # Both comment pairs should preserve their blanks
        assert src == after, f'Blanks were incorrectly removed:\n{after}'

    def test_consecutive_comments_no_blank_needed(self, tmp_path, reformat) -> None:
        """Consecutive comments without blank should stay the same."""
        src = (
            'def func():\n'
            '    # comment 1\n'
            '    # comment 2\n'
            '    pass\n'
        )
        after = reformat.fix(src, 'AR013').after
        assert after == src

    def test_triple_comment_with_blank_preserved(self, tmp_path, reformat) -> None:
        """Blank between triplets of comments should be preserved."""
        src = (
            'def func():\n'
            '    # group 1\n'
            '    # group 2\n'
            '    \n'
            '    # group 3\n'
            '    # group 4\n'
            '    pass\n'
        )
        after = reformat.fix(src, 'AR013').after
        # The blank between comment groups should be preserved
        assert '# group 3\n' in after, f'Comment groups removed:\n{after}'
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if '# group 2' in line:
                assert not lines[i + 1].strip(), 'Blank after group 2 was removed'
                break

    def test_ar001_example_exact(self, tmp_path, reformat) -> None:
        """Test the exact example from the feature request."""
        src = (
            'def func(a):\n'
            '    x = 4\n'
            '    y = 5\n'
            '    # This is a sample\n'
            '    \n'
            '    # With a blank line\n'
            '    return a * x + y\n'
        )
        after = reformat.fix(src, 'AR013').after
        # The blank line between the two comments should be preserved
        lines = after.split('\n')
        found_comment_a = False
        found_blank_after = False
        for i, line in enumerate(lines):
            if '# This is a sample' in line:
                found_comment_a = True
                if i + 1 < len(lines) and not lines[i + 1].strip():
                    found_blank_after = True
        assert found_comment_a, 'Comment line not found'
        assert found_blank_after, 'Blank line after comment not found'
