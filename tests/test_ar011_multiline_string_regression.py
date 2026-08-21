"""Regression test for AR011 bug: blank lines inside multi-line strings removed.

AR011 must never remove or report lines that are merely blank *within* a
multi-line string literal.  The bug appeared because AR011 performs pure
text-indent analysis (it never consults ``find_string_lines`` / the tokenizer),
so an "indent entry" transition whose two non-blank lines both happen to fall
inside a multi-line string was treated as a real block boundary and the blank
lines between them -- which are actually part of the string content -- were
deleted, corrupting the string.

AR012/AR013/AR014 are all string-aware for this reason; AR011 now is too.
"""
from __future__ import annotations

import sys
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str]:
    """Run agent-reformat fix mode on a temp file. Returns (original, modified)."""
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


def run_check(tmp_path: Path, source_code: str) -> tuple[str, int]:
    """Run agent-reformat in check mode. Returns (stdout, rc). Source untouched."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = __import__('io').StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--rules', 'AR011'])
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
        else:
            rc = 0
    finally:
        sys.stdout = original_stdout
    return captured.getvalue(), rc


class TestAR011MultilineStringRegression:
    """Blank lines inside multi-line strings survive AR011."""

    def test_blank_inside_string_preserved(self, tmp_path: Path) -> None:
        """Blank lines between an indent 'transition' that both live inside a
        multi-line string must NOT be removed.
        """
        src = 'x = """\nx\n\n\n    y\n"""\nz = 1\n'
        original, after = run_fix(tmp_path, src)
        # The blank lines inside the string must survive verbatim.
        assert 'x\n\n\n    y' in after, f'blanks inside string were stripped:\n{after}'
        # The whole thing should be byte-for-byte unchanged (only the string
        # contained a transition; there is no real indentation block to fix).
        assert after == original, f'file was modified:\n{after}'

    def test_string_interior_not_a_transition(self, tmp_path: Path) -> None:
        """The same structure inside a function body is still protected."""
        src = 'def foo():\n    x = """\n    a\n\n\n        b\n    """\n    return 1\n'
        original, after = run_fix(tmp_path, src)
        assert 'a\n\n\n        b' in after, f'blanks inside string were stripped:\n{after}'
        assert after == original, f'file was modified:\n{after}'

    def test_check_mode_no_violation_inside_string(self, tmp_path: Path) -> None:
        """Check mode must report no violation for a transition that is only
        inside a string literal.
        """
        src = 'x = """\nx\n\n\n    y\n"""\n'
        stdout, rc = run_check(tmp_path, src)
        assert rc == 0, f'expected clean exit, got {rc}\nstdout={stdout}'
        assert 'AR011' not in stdout, f'AR011 should not fire on string interior:\n{stdout}'

    def test_real_blank_outside_string_still_removed(self, tmp_path: Path) -> None:
        """AR011 must still fix a genuine indent-entry blank that is NOT inside
        a string (i.e. the string awareness did not disable the rule).
        """
        src = 'def foo():\n\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'def foo():\n    pass\n'

    def test_real_blank_near_string_still_removed(self, tmp_path: Path) -> None:
        """A genuine entry blank right before a real (non-string) indented body
        is still removed, even though the body contains a multi-line string.
        """
        src = 'def foo():\n\n    x = "a\\nb"\n    return x\n'
        _, after = run_fix(tmp_path, src)
        # Entry blank removed; the 2-char string literal is untouched.
        assert after == 'def foo():\n    x = "a\\nb"\n    return x\n', f'got:\n{after}'
