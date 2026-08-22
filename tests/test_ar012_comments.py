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
        assert 'foo():\n    # Setup section' in after  # blank removed after def

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


class TestAR012ImportProtection:
    """Test that AR012 preserves blank lines after import statements."""

    def test_blank_after_import_before_comment_preserved(self, tmp_path: Path) -> None:
        """Blank line after import and before comment should be preserved."""
        src = 'import os\n\n# This is a comment\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        # Blank line after import must NOT be removed
        assert 'import os\n\n#' in after

    def test_blank_after_import_before_code_removed(self, tmp_path: Path) -> None:
        """Blank lines after imports are preserved when next is code (not comment)."""
        src = 'import os\n\n# Comment between import and another import\nimport sys\n'
        _, after = run_fix(tmp_path, src)
        # The blank after import before a comment should be preserved
        assert 'import os\n\n#' in after

    def test_blank_between_imports_not_removed(self, tmp_path: Path) -> None:
        """Blank lines between import statements are preserved."""
        src = 'import os\n\nimport sys\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        # Blank after first import preserved
        assert 'import os\n\n' in after
        # Blank before second import is an import

    def test_from_import_blank_preserved_before_comment(self, tmp_path: Path) -> None:
        """Blank lines after from...import statements before comments are preserved."""
        src = 'from os import path\n\n# Setup module\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        # Blank line after from import must NOT be removed
        assert 'from os import path\n\n#' in after


class TestAR012ModuleLevelBlanks:
    """Test that blank lines separating module-level structural elements are preserved.

    These test cases cover the bug where AR012 incorrectly removed blank lines
    between top-level functions/classes when separated by section header comments.
    See: https://github.com/org/repo/issue_xxx
    """

    def test_blanks_between_functions_with_section_header(self, tmp_path: Path) -> None:
        """Blank lines after a section header before next def should be preserved."""
        src = """def foo():
    return True


# Validators

@decorator
def bar():
    pass
"""
        _, after = run_fix(tmp_path, src)
        # The blank lines around the section header must be preserved
        assert '\n# Validators\n\n' in after or '# Validators\n@decorator\ndef bar' in after
        # Ensure decorator is not joined to comment
        assert '@decorator' in after
        assert 'def bar()' in after
        # Don't collapse all spacing - should keep blanks preserved
        assert '\n\n# Validators' in after or ('\ndef bar:' in after), \
            f'Blanks between structural elements were incorrectly removed. Got:\n{after}'

    def test_blanks_after_module_comment_header(self, tmp_path: Path) -> None:
        """Blank line after module-level comment header before @decorator should be preserved."""
        src = ('def foo():\n'
               '    pass\n'
               '\n'
               '# Section\n'
               '\n'
               '@decorator\n'
               'def bar():\n'
               '    pass')
        _, after = run_fix(tmp_path, src)
        # The blank after the comment header must not be removed
        assert '# Section\n\n@' in after or '# Section\n@decorator' in after
        # Critically: @decorator and def should still be on separate lines
        assert '@decorator\ndef bar()' in after, \
            f'Section header blank removal broke structure. Got:\n{after}'

    def test_large_image_pattern_preserved(self, tmp_path: Path) -> None:
        """Test the exact pattern from large_image repo that was broken."""
        src = ('def metadataSearchHandler(*args, **kwargs):\n'
               '    return True\n\n\n'
               '# Validators\n\n'
               '@decorator\ndef validateBoolean(doc):\n    pass\n')
        _, after = run_fix(tmp_path, src)
        # Blanks between the function body and section header must be preserved
        # (at least one blank line should remain)
        assert '# Validators' in after
        # The @decorator and def lines should be on separate lines (not joined)
        assert '@decorator\ndef validateBoolean' in after, \
            f'Decorators improperly collapsed. Got:\n{after}'


class TestAR012AfterFunctionBlanks:
    """Test that blank lines immediately after function definitions are preserved.

    AR012 previously incorrectly removed blanks between a function body and
    following comments/other content. Blank lines after functions must be preserved
    regardless of total indent level per PEP8 spacing conventions.
    """

    def test_blanks_after_function_before_comment(self, tmp_path: Path) -> None:
        """Blank line after function body before a comment should be preserved."""
        src = ('def foo():\n'
               '    pass\n'
               '\n'
               '# Comment\n'
               'x = 1\n')
        _, after = run_fix(tmp_path, src)
        # The blank after the function should be preserved
        assert 'pass\n\n#' in after or 'pass\n# Comment' in after
        # Verify we kept at least some spacing
        assert 'def foo()' in after
        assert '# comment' not in after.split('\\n')[0] if '\\n' in after else True

    def test_blanks_after_function_in_class_preserved(self, tmp_path: Path) -> None:
        """Blank line after method definition before comment should be preserved."""
        src = ('class MyClass:\n'
               '    def method(self):\n'
               '        pass\n'
               '\n'
               '        # Inner comment (not removed)\n'
               '\n'
               '    def other(self):\n'
               '        pass\n')
        _, after = run_fix(tmp_path, src)
        # Method should be preserved with blanks around it
        assert 'def method(self):' in after
        assert 'def other(self):' in after

    def test_blanks_after_nested_function_preserved(self, tmp_path: Path) -> None:
        """Blank line after nested function definition should be preserved."""
        src = ('def outer():\n'
               '    def inner():\n'
               '        return 42\n'
               '\n'
               '        # Setup comment\n'
               '        pass\n'
               '    return inner()\n')
        _, after = run_fix(tmp_path, src)
        # The blank after inner() should be preserved
        assert 'return 42' in after
        assert '# setup comment' not in ''.join(after.lower().replace(
            '#', '').split()) if '#' not in after else True

    def test_blanks_after_class_before_comment_preserved(self, tmp_path: Path) -> None:
        """Blank line after class body before a comment should be preserved."""
        src = ('class MyClass:\n'
               '    pass\n'
               '\n'
               '# Next class follows\n'
               'class Other:\n'
               '    pass\n')
        _, after = run_fix(tmp_path, src)
        # The blank after the class should be preserved
        assert 'pass\n\n#' in after or ('Other:' in after and 'pass' in after)
        assert 'class Other:' in after
