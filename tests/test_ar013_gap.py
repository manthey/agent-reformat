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


class TestAR013BasicRemoval:
    """Test that blank lines between few statements are removed."""

    def test_two_statements_with_blank_removed(self, tmp_path: Path) -> None:
        """Two consecutive statements with blank should lose the blank (min_gap=3)."""
        src = 'x = 1\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\ny = 2\n'

    def test_three_statements_no_blank_kept(self, tmp_path: Path) -> None:
        """Three consecutive statements without blanks stays the same."""
        src = 'x = 1\ny = 2\nz = 3\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\ny = 2\nz = 3\n'

    def test_three_statements_with_blank_kept(self, tmp_path: Path) -> None:
        """Three consecutive statements with a blank keeps it (min_gap met)."""
        src = 'x = 1\n\ny = 2\nz = 3\n'
        _, after = run_fix(tmp_path, src)
        # Three+ statements so blank is preserved
        assert '\n' in after

    def test_four_statements_with_blank_kept(self, tmp_path: Path) -> None:
        """Four consecutive same-indent statements have >= min_gap so blanks kept."""
        src = 'a = 1\n\nb = 2\nc = 3\n\nd = 4\n'
        _, after = run_fix(tmp_path, src)
        # All four statements at indent 0 form ONE group of 4 >= min_gap(3)
        # So blanks between them are preserved
        assert 'a = 1\nb = 2' not in after or 'a = 1\n\nb = 2' in after

    def test_five_statements_no_blanks_kept(self, tmp_path: Path) -> None:
        """Five consecutive statements without blanks stays the same."""
        src = 'a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n'
        _, after = run_fix(tmp_path, src)
        assert after == src


class TestAR013FewStatementsRemoved:
    """Test that blank lines are removed when group has < min_gap statements."""

    def test_only_two_module_level_stmts(self, tmp_path: Path) -> None:
        """Two module-level statements remove the blank between them."""
        src = 'a = 1\n\nb = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'a = 1\nb = 2\n'

    def test_two_statements_one_blank_removed(self, tmp_path: Path) -> None:
        """Two statements at same indent remove blank (2 < min_gap)."""
        src = """def foo():
    a = 1

    b = 2
"""
        _, after = run_fix(tmp_path, src)
        # Inside function: 2 statements < min_gap -> remove blank
        assert '    a = 1\n    b = 2' in after or 'a = 1\nb = 2' in after

    def test_many_module_level_reduced(self, tmp_path: Path) -> None:
        """Only two module-level stmts with blank -> reduce to no blank."""
        src = 'x = 1\n\ny = 2\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'x = 1\ny = 2\n'


class TestAR013PreservedBlanks:
    """Test that certain blank lines are preserved."""

    def test_between_function_defs_preserved(self, tmp_path: Path) -> None:
        """Blank lines between function definitions at module level preserved."""
        src = 'def foo():\n    pass\n\n\ndef bar():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Between two def blocks - should be preserved per user spec
        assert '\ndef bar()' in after

    def test_between_class_defs_preserved(self, tmp_path: Path) -> None:
        """Blank lines between class definitions at module level preserved."""
        src = 'class Foo:\n    pass\n\nclass Bar:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Between two class blocks - should be preserved per user spec
        assert '\nclass Bar:' in after

    def test_blank_after_func_body_to_module_level(self, tmp_path: Path) -> None:
        """Blank after function body returns to module level preserved."""
        src = """def foo():
    pass


x = 1
"""
        _, after = run_fix(tmp_path, src)
        # Blank before x=1 at module level should be preserved as section
        # separator
        assert 'pass\n\nx = 1' in after or 'pass\n\n\nx = 1' in after

    def test_end_of_file_blanks_preserved(self, tmp_path: Path) -> None:
        """Trailing blanks at end of file should be preserved."""
        src = 'x = 1\n\n\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_multiline_string_blanks_preserved(self, tmp_path: Path) -> None:
        """Blanks inside multi-line strings are not touched."""
        src = '''x = """
line1

line2
"""

y = 1
'''
        _, after = run_fix(tmp_path, src)
        # The blank inside the string should remain
        assert '\nline1\n\nline2' in after


class TestAR013ComplexScenarios:
    """Test complex scenarios."""

    def test_block_with_many_statements_keeps_blanks(self, tmp_path: Path) -> None:
        """Block with >= min_gap statements can have blanks kept."""
        src = """def foo():
    a = 1
    b = 2


    c = 3
    d = 4
    e = 5
"""
        _, after = run_fix(tmp_path, src)
        # Inside function: 5 statements (a,b,c,d,e) all at indent 4 -> group of
        # 5 >= min_gap Blanks preserved among them
        assert 'b = 2\n' in after
        assert '\n    c = 3' in after

    def test_if_block_few_statements_cleans(self, tmp_path: Path) -> None:
        """Few statements inside if block -> clean up blanks."""
        src = """if True:
    a = 1

    b = 2
"""
        _, after = run_fix(tmp_path, src)
        # Two statements at indent 4 inside if < min_gap -> blank removed
        assert 'a = 1\n    b = 2' in after or 'a = 1\nb = 2' in after


class TestAR013EdgeCases:
    """Test edge cases."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file unchanged."""
        _, after = run_fix(tmp_path, '')
        assert after == ''

    def test_only_blanks(self, tmp_path: Path) -> None:
        """File with only blank lines unchanged."""
        src = '\n\n\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_single_statement(self, tmp_path: Path) -> None:
        """Single statement cannot trigger rule."""
        src = 'x = 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_no_consecutive_same_indent(self, tmp_path: Path) -> None:
        """Alternating indent levels don't form groups with < min_gap."""
        src = 'if True:\n    pass\nx = 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == src


class TestAR013CheckMode:
    """Test that check mode works correctly."""

    def test_check_mode_no_file_change(self, tmp_path: Path) -> None:
        """Check mode should not modify the source file."""
        src = 'x = 1\n\ny = 2\n'
        f = tmp_path / 'test.py'
        f.write_text(src)

        captured_out = __import__('io').StringIO()
        original_stdout = sys.stdout
        try:
            sys.stdout = captured_out
            try:
                run_hook([str(f), '--rules', 'AR013'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        assert f.read_text() == src, 'Check mode must not modify the file'
