"""Regression test for AR013 bug: statements near STRING args skipped too aggressively.

This tests the fix for a bug where collect_stmt_starts' skip condition used
a fixed +-2 offset around statement lines to check for STRING token proximity.
This caused false positives when:
1. The statement's own arguments are STRING literals (e.g., events.bind('data.process'))
2. A previous/next multiline call also uses STRING arguments

In these cases the statement gets incorrectly skipped, preventing AR013 from
finding the short group and cleaning up blank lines that should be removed.

The fix changes collect_stmt_starts to only skip statements that fall INSIDE
a multi-line STRING token (where start_line <= line <= end_line), not just
any statement within a fixed offset of having a STRING on its line.
"""
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
    f_content = f.read_text()
    return source_code, f_content


class TestAR013StringArgsRegression:
    """Blank lines after function calls with STRING args should be cleaned up by AR013."""

    def test_blank_between_method_calls_with_string_args(self, tmp_path: Path) -> None:
        """Blank between events.bind(...) and search.pop() should be removed.

        Both statements contain STRING literal arguments but are valid
        executable statements whose group has < min_gap consecutive items.
        The blank line between them should be removed because the two
        indent-4 statements inside load() form a short group (< min_gap=3).
        """
        src = """def load():
    events.bind(
        'data.process', 'large_image_annotation.annotations',
        handlers.process_annotations)

    search._allowedSearchMode.pop('key', None)
"""
        _, after = run_fix(tmp_path, src)
        # Two indent-4 statements (< min_gap=3), blank should be removed
        assert 'process_annotations)\n    search' in after, (
            f'Blank between calls was not removed! Output:\n{after}'
        )

    def test_simple_two_stmts_with_string_args(self, tmp_path: Path) -> None:
        """Two simple statements each with STRING arguments - blank between removed."""
        src = """def foo():
    call_me('arg1', 'arg2')

    next_fn('data')
"""
        _, after = run_fix(tmp_path, src)
        # Two indent-4 statements (< min_gap=3), blank should be removed
        # Before fix: blank was preserved because stmts were skipped
        assert "'arg1', 'arg2'" in after
        assert 'next_fn' in after
        # Verify the blank line is actually gone (no double newline between)
        assert "'arg1', 'arg2')\n\n    next_fn" not in after, (
            f'Blank line between string-arg calls was not removed! Output:\n{after}'
        )


class TestAR013MultilineCallWithNeighborStrings:
    """Statements near multiline STRING calls still get processed correctly."""

    def test_between_multiline_calls_blank_removed(self, tmp_path: Path) -> None:
        """Blank between a multiline call (ending with boolean arg) and next statement
        should still be removed even if adjacent to other statements using strings.
        """
        src = """def load():
    info.x.method(
        'copyAnnotations', 'Copy annotations when copying resources)',
        required=False, dataType='boolean')

    search.pop('metadata', None)
"""
        _, after = run_fix(tmp_path, src)
        # Two indent-4 statements (< min_gap=3), blank should be removed
        assert "'boolean')\n\n    search" not in after, (
            f'Blank between multiline call and next statement was NOT removed! Output:\n{after}'
        )


class TestAR013NoFalsePositives:
    """Ensure the fix doesn't accidentally break valid protection."""

    def test_multiline_string_blanks_preserved(self, tmp_path: Path) -> None:
        """Verify blank lines INSIDE genuine multi-line strings are preserved."""
        src = '''def foo():
    text = """
    hello

    world
    """


    next_fn()
'''
        _, after = run_fix(tmp_path, src)
        # The blank inside the multiline string should remain
        assert 'hello\n\n    world' in after
