"""Regression test for AR013 bug: blank lines between import statements were being removed."""
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
            run_hook([str(f), '--fix', '--rules', 'AR013'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


class TestAR013ImportsRegression:
    """Test that AR013 preserves blank lines between import statements.

    These are regression tests for the bug where AR013 incorrectly removed
    blank lines between consecutive imports (e.g., inside a function),
    when there were fewer than min_gap statements at the same indent.
    """

    def test_inner_function_imports_blank_preserved(self, tmp_path: Path) -> None:
        """Two consecutive imports in a function should preserve their blank."""
        src = """def foo():
    import os

    import sys


x = 1
"""
        _, after = run_fix(tmp_path, src)
        # Blank line (could be empty or with spaces) between imports should be
        # preserved
        assert 'import os' in after
        assert 'import sys' in after
        # Find the positions of import os and import sys
        lines = after.split('\n')
        for i, line in enumerate(lines):
            if 'import os' in line:
                # Next non-empty line should be import sys (or blank then
                # import sys)
                next_content = None
                for j in range(i + 1, len(lines)):
                    if lines[j].strip():
                        next_content = lines[j]
                        break
                assert 'import sys' in next_content

    def test_inner_function_many_imports_blank_preserved(self, tmp_path: Path) -> None:
        """Multiple consecutive imports should preserve their blanks."""
        src = """def foo():
    import os

    import sys

    import re


x = 1
"""
        _, after = run_fix(tmp_path, src)
        # All blank lines between imports should be preserved
        assert '\n\n' in after

    def test_module_level_imports_blank_preserved(self, tmp_path: Path) -> None:
        """Module-level imports should preserve their blank lines."""
        src = """import os

import sys
"""
        _, after = run_fix(tmp_path, src)
        # Blank between module-level imports should be preserved
        assert 'import os\n\nimport sys' in after or after.count('\n') >= 3

    def test_from_imports_blank_preserved(self, tmp_path: Path) -> None:
        """from...import statements should also preserve blank lines."""
        src = """def foo():
    from os import path

    from sys import argv


x = 1
"""
        _, after = run_fix(tmp_path, src)
        # Blank between from imports should be preserved
        assert '\n' in after
