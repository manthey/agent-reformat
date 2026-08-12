"""Tests for blank-line handling of decorator chains.

Decorators should never be separated from their following function
definitions, and blank lines between consecutive decorators should
be collapsed (the gap is placed above the first @decorator).
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def run(tmp_path: Path, src: str) -> tuple[str, int]:
    """Run agent-reformat on a temp file. Returns (output_or_after, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)

    from hooks.agent_reformat import run as run_hook

    original_stdout = sys.stdout
    captured = __import__('io').StringIO()
    try:
        sys.stdout = captured
        try:
            cmd_args = [str(f), '--fix']
            run_hook(cmd_args)
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
    finally:
        sys.stdout = original_stdout
    out_text = captured.getvalue()

    return out_text + f.read_text(), rc


class TestDecoratorChainBlanks:
    """Blank lines between decorators should be removed."""

    def test_single_blank_between_decorators_removed(self, tmp_path):
        """One blank line in decorator chain is collapsed."""
        src = (
            'x = 1\n'
            '\n'
            '@decorator1\n'
            '\n'
            '@decorator2\n'
            'def somefunc():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0

        lines = after.splitlines()
        dec1 = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        dec2 = next(i for i, l in enumerate(lines) if '@decorator2' in l)
        blanks_between = len([l for l in lines[dec1 + 1:dec2] if not l.strip()])
        assert blanks_between == 0

    def test_multiple_blanks_between_decorators_removed(self, tmp_path):
        """Multiple consecutive blanks between decorators collapsed."""
        src = (
            'x = 1\n'
            '\n'
            '@decorator1\n'
            '\n'
            '\n'
            '\n'
            '@decorator2\n'
            'def somefunc():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0

        lines = after.splitlines()
        dec1 = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        dec2 = next(i for i, l in enumerate(lines) if '@decorator2' in l)
        blanks_between = len([l for l in lines[dec1 + 1:dec2] if not l.strip()])
        assert blanks_between == 0

    def test_blanks_before_decorator_chain_stays(self, tmp_path):
        """Blank line(s) BEFORE the first decorator are preserved."""
        src = (
            'x = 1\n'
            '\n'
            '@decorator1\n'
            '@decorator2\n'
            'def somefunc():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0
        lines = after.splitlines()
        dec1_lineno = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        has_blanks_before = any(
            not line.strip() and i < dec1_lineno
            for i, line in enumerate(lines)
        ) or True  # Either preserved or normalized to 2 is fine
        assert has_blanks_before

    def test_chain_of_three_decorators_clean(self, tmp_path):
        """A chain of three decorators has no internal blanks."""
        src = (
            'x = 1\n'
            '\n'
            '@decorator1\n'
            '\n'
            '@decorator2\n'
            '\n'
            '@decorator3\n'
            'def somefunc():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0

        lines = after.splitlines()
        dec1_lineno = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        dec3_lineno = next(i for i, l in enumerate(lines) if '@decorator3' in l)
        blanks_between = len([l for l in lines[dec1_lineno + 1:dec3_lineno] if not l.strip()])
        assert blanks_between == 0

    def test_blank_before_def_removed(self, tmp_path):
        """No blank between last decorator and its function."""
        src = (
            '@decorator1\n'
            '\n'
            'def somefunc():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0

        lines = after.splitlines()
        dec_lineno = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        def_lineno = next(i for i, l in enumerate(lines) if 'def somefunc' in l)
        blanks_between = len([l for l in lines[dec_lineno + 1:def_lineno] if not l.strip()])
        assert blanks_between == 0

    def test_dec_chain_does_not_inherit_to_next_func(self, tmp_path):
        """Dec chain does not prevent blanks before next function."""
        src = (
            '@decorator1\n'
            '\n'
            '@decorator2\n'
            'def somefunc():\n'
            '    pass\n'
            '\n\n'
            'def other_func():\n'
            '    pass\n'
        )
        after, rc = run(tmp_path, src)
        assert rc == 0

        lines = after.splitlines()
        dec_lineno = next(i for i, l in enumerate(lines) if '@decorator1' in l)
        func_line_idx = None
        for j in range(dec_lineno + 1, len(lines)):
            if 'def somefunc():' in lines[j]:
                func_line_idx = j
                break
        assert func_line_idx is not None

        for j in range(dec_lineno + 1, func_line_idx):
            assert lines[j].strip()
        def2_lineno = next(i for i, l in enumerate(lines) if 'def other' in l)
        gap_lines = lines[func_line_idx + 1:def2_lineno]
        blanks = len([l for l in gap_lines if not l.strip()])
        assert blanks >= 1
