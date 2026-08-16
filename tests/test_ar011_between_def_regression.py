"""Regression tests for AR011 bug: blank lines between def statements were incorrectly removed."""
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
            run_hook([str(f), '--fix', '--rules', 'AR011'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


class TestAR011BetweenDefRegression:
    """Test that AR011 preserves blank lines between def statements at the same containing level.

    This catches the bug where AR011 incorrectly removed blanks that separate
    sibling definitions (methods in a class, or functions at module level).
    """

    def test_blank_between_class_methods_preserved(self, tmp_path: Path) -> None:
        """Blank lines between methods inside a class should be preserved."""
        src = """class Foo:
    def method(self):
        pass

    def another_method(self):
        pass

"""
        _, after = run_fix(tmp_path, src)
        # Blank before 'def another_method' must be preserved
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'def another_method' in line and i > 0:
                assert not lines[i - 1].strip(), \
                    'Blank line before def another_method was removed!'
                break

    def test_blank_between_module_functions_preserved(self, tmp_path: Path) -> None:
        """Blank line between module-level function definitions should be preserved."""
        src = 'def foo(): pass\n\n\ndef bar(): pass\n'
        _, after = run_fix(tmp_path, src)
        # Module-level func defs have 2+ blank lines between them for
        # separation
        assert '\n\n\n' in after or '\n\n' in after.replace('pass', ''), \
            'Blank line between module-level functions was removed!'

    def test_blank_after_function_before_module_var_preserved(self, tmp_path: Path) -> None:
        """Blank line after a function body (returning to lower indent) should be preserved."""
        src = """def foo():
    return 1


x = 2
"""
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'return 1' in line:
                # Find next blank/variable - preserve at least one blank
                found_blank_after = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    if not lines[j].strip():
                        found_blank_after = True
                        break
                    if 'x =' in lines[j]:
                        break
                assert found_blank_after or i + 1 >= len(lines) - 1, \
                    'Blank after function body was removed!'
                break

    def test_blank_between_func_and_class_preserved(self, tmp_path: Path) -> None:
        """Blank between func and class at module level should be preserved."""
        src = 'def foo(): pass\n\nclass Bar:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Module-level separation preserved
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'class Bar' in line and i > 0:
                assert not lines[i - 1].strip(), \
                    'Blank before class was removed!'
                break

    def test_nested_scope_outdent_blank_preserved(self, tmp_path: Path) -> None:
        """When inside a nested block, blank to sibling scope level preserved."""
        src = """def outer():
    if True:
        x = 1

    y = 2

"""
        _, after = run_fix(tmp_path, src)
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'y = 2' in line and i > 0:
                # Blank should be preserved because we're in the same 'outer()'
                # body
                assert not lines[i - 1].strip(), \
                    'Blank between nested block and code at same level was removed!'
                break
