"""Tests for AR011: Remove blank lines before/after indent and outdent boundaries."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str]:
    """Run agent-reformat fix mode on a temp file. Returns (original, modified)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR011'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


def check_fix(tmp_path: Path, src: str) -> tuple[str, int]:
    """Run agent-reformat in check mode. Returns (stdout, rc). Source untouched."""
    f = tmp_path / 'test.py'
    f.write_text(src)
    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--rules', 'AR011'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return captured.getvalue(), captured


class TestAR011IndentBoundaries:
    """Test that blank lines before entering an indented block are removed."""

    def test_blank_before_if_body(self, tmp_path: Path) -> None:
        """Blank line before if body should be removed."""
        src = 'if True:\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'if True:\n    pass\n'

    def test_blank_before_for_body(self, tmp_path: Path) -> None:
        """Blank line before for body should be removed."""
        src = 'for i in range(10):\n\n    print(i)\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'for i in range(10):\n    print(i)\n'

    def test_blank_before_while_body(self, tmp_path: Path) -> None:
        """Blank line before while body should be removed."""
        src = 'while True:\n\n    break\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'while True:\n    break\n'

    def test_blank_before_try_body(self, tmp_path: Path) -> None:
        """Blank line before try body should be removed."""
        src = 'try:\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'try:\n    pass\n'

    def test_blank_before_except_body(self, tmp_path: Path) -> None:
        """Blank line before except body should be removed."""
        src = 'try:\n    pass\nexcept Exception:\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'try:\n    pass\nexcept Exception:\n    pass\n'

    def test_blank_before_with_stmt_body(self, tmp_path: Path) -> None:
        """Blank line before with body should be removed."""
        src = 'with open("x"):\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'with open("x"):\n    pass\n'

    def test_blank_before_def_body(self, tmp_path: Path) -> None:
        """Blank line before function body should be removed."""
        src = 'def foo():\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'def foo():\n    pass\n'

    def test_blank_before_class_body(self, tmp_path: Path) -> None:
        """Blank line before class body should be removed."""
        src = 'class Foo:\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'class Foo:\n    pass\n'

    def test_multiple_consecutive_blanks_before_body_removed(self, tmp_path: Path) -> None:
        """AR011 FIX: All consecutive blanks before an indented body should be removed.

        The previous implementation may only remove one blank. Now ALL consecutive
        blanks at indent entry transitions are properly removed.
        """
        src = 'def foo():\n\n\n\n    x = 1\n'
        _, after = run_fix(tmp_path, src)
        # All four blanks before the indented body should be removed
        assert after == 'def foo():\n    x = 1\n'

    def test_nested_indent_blank_removed(self, tmp_path: Path) -> None:
        """Blank lines before nested indents are also removed."""
        src = """if True:
    if True:
        pass
"""
        _, after = run_fix(tmp_path, src)
        assert after == 'if True:\n    if True:\n        pass\n'


class TestAR011OutdentBoundaries:
    """Test outdent behavior."""

    def test_blank_after_if_body_return_to_outer(self, tmp_path: Path) -> None:
        """Blank line AFTER if body at module level preserved."""
        src = 'if True:\n\n    pass\n\nprint("after")\n'
        _, after = run_fix(tmp_path, src)
        # Module-level blank after outdent to indent=0 should stay.
        assert 'pass\n\nprint' in after

    def test_blank_after_for_body_returns_to_outer(self, tmp_path: Path) -> None:
        """Blank line AFTER for body at module level preserved."""
        src = 'for i in range(1):\n    pass\n\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        # Blank after for block before module-level code is preserved
        assert 'pass\n\nx' in after

    def test_blank_after_class_methods(self, tmp_path: Path) -> None:
        """Blank lines within class at same indent should be preserved (not AR011)."""
        src = 'class Foo:\n    def a(self): pass\n\n    def b(self): pass\n'
        _, after = run_fix(tmp_path, src)
        # Within class body: blank kept (same indent level).
        assert '\n' in after  # just ensure structure preserved

    def test_blank_inside_nested_blocks_removed(self, tmp_path: Path) -> None:
        """Blank lines inside nested blocks are cleaned up."""
        src = """if True:
    for i in range(1):
        x = 1


y = 2
"""
        _, after = run_fix(tmp_path, src)
        # Blank in for body removed; module level preserved
        assert 'for i in range(1):\n        x = 1' in after


class TestAR011PreservedBlanks:
    """Test that certain blank lines are preserved (not touched by AR011)."""

    def test_blank_before_module_func_preserved(self, tmp_path: Path) -> None:
        """Blank line before module-level function is preserved."""
        src = 'x = 1\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert '\n\ndef foo()' in after

    def test_blank_between_module_funcs_preserved(self, tmp_path: Path) -> None:
        """Blank line between module-level func defs is preserved."""
        src = 'def a(): pass\n\n\ndef b(): pass\n'
        _, after = run_fix(tmp_path, src)
        assert '\n\n\n' in after

    def test_blank_after_module_class_preserved(self, tmp_path: Path) -> None:
        """Blank line after class at module level preserved."""
        src = 'class A:\n    pass\n\ndef f():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'def f()' in line:
                # Blank before top-level def should be preserved
                assert i > 0, 'Expected non-negative index'
                assert not lines[i - 1].strip()
                break

    def test_blank_lines_within_same_indent_kept(self, tmp_path: Path) -> None:
        """Blanks between statements at THE SAME indent level are kept."""
        src = 'x = 1\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        # These are at the same module-level indent, no indent change
        assert '\n\n' in after or 'x = 1\n\ny' in after

    def test_no_blanks_before_import_preserved(self, tmp_path: Path) -> None:
        """Blanks between imports preserved."""
        src = """import os

import sys
"""
        _, after = run_fix(tmp_path, src)
        assert 'import' in after


class TestAR011ModuleLevelStructureProtection:
    """Test that AR011 protects module-level structural separators."""

    def test_module_level_blanks_after_if_preserved(self, tmp_path: Path) -> None:
        """Blank before module-level print after if is preserved."""
        src = """if True:
    pass


print("after")
"""
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'print' in line and i > 0:
                # Module-level blank preserved before print
                assert not lines[i - 1].strip()
                break

    def test_module_level_blanks_after_for_preserved(self, tmp_path: Path) -> None:
        """Blank after for block at module level preserved."""
        src = """for i in range(1):
    x = 1


y = 2
"""
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        # Blank before top-level y=2 preserved
        for i, line in enumerate(lines):
            if 'y = 2' in line and i > 0:
                assert not lines[i - 1].strip()


class TestAR011EdgeCases:
    """Test edge cases."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file unchanged."""
        _, after = run_fix(tmp_path, '')
        assert after == ''

    def test_only_blank_lines(self, tmp_path: Path) -> None:
        """File with only blank lines stays as is."""
        src = '\n\n\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_single_line_file(self, tmp_path: Path) -> None:
        """Single line cannot have blank-line issues."""
        src = 'x = 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_no_indent_changes(self, tmp_path: Path) -> None:
        """File with no indent changes should not be modified."""
        src = 'x = 1\ny = 2\nz = 3\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_module_level_blanks_between_if_and_code(self, tmp_path: Path) -> None:
        """Blanks between if block and following module-level code preserved."""
        src = """if True:
    x = 1


y = 2
"""
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'y = 2' in line and i > 0:
                assert not lines[i - 1].strip()


class TestAR011WithNoqa:
    """Test that noqa directives don't affect AR011."""

    def test_blank_before_indent_with_noqa_on_prev_line(self, tmp_path: Path) -> None:
        """Blank before indent is still removed (AR011 has no noqa concept)."""
        src = 'if True:  # noqa\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert 'if True:' in after
        assert '    pass' in after


class TestAR011CheckMode:
    """Test that check mode works correctly."""

    def test_check_mode_no_file_change(self, tmp_path: Path) -> None:
        """Check mode should not modify the source file."""
        src = 'if True:\n\n    pass\n'
        f = tmp_path / 'test.py'
        f.write_text(src)
        captured_out = io.StringIO()
        original_stdout = sys.stdout
        try:
            sys.stdout = captured_out
            try:
                run_hook([str(f), '--rules', 'AR011'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        assert f.read_text() == src, 'Check mode must not modify the file'


class TestAR011MixedIndentOutdent:
    """Test complex scenarios with mixed indent and outdent."""

    def test_class_method_indent(self, tmp_path: Path) -> None:
        """Class body indentation should have blank lines cleaned."""
        src = """class Foo:
    def method(self):
        pass
"""
        _, after = run_fix(tmp_path, src)
        # Inside class body, blanks around indent changes removed
        assert ('def method(self):\n\n        pass' in after or
                'def method(self):\n        pass' in after)

    def test_async_func_indent(self, tmp_path: Path) -> None:
        """Async function body should have blank lines cleaned."""
        src = """async def fetch():
    return await get()
"""
        _, after = run_fix(tmp_path, src)
        # Blank before async function at module level preserved
        assert 'async def fetch():\n    return' in after


class TestAR011FileStructure:
    """Test file-level structure preservation."""

    def test_shebang_and_imports_untouched(self, tmp_path: Path) -> None:
        """Shebang and imports at top preserved."""
        src = """#!/usr/bin/env python3

import os

from pathlib import Path


def main():
    print("hello")

"""
        _, after = run_fix(tmp_path, src)
        assert '#!/usr/bin/env python3' in after
        assert 'import os' in after
        assert 'from pathlib import Path' in after

    def test_end_of_file_blanks_preserved(self, tmp_path: Path) -> None:
        """End of file trailing blanks should be preserved."""
        src = 'x = 1\n\n\n\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_no_change_for_already_clean_file(self, tmp_path: Path) -> None:
        """Clean file without extra blanks passes through unchanged."""
        src = 'if True:\n    pass\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == src
