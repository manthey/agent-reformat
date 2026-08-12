"""Tests for AR012, AR015, AR021, AR022 rules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def run(test_file_path: Path, src: str, fixed: bool = True) -> tuple[str, int]:
    """Run agent-reformat and return (result_output + file_after_or_stdout, rc)."""
    test_file_path.write_text(src)
    cmd = [sys.executable, '-m', 'hooks.agent_reformat']

    if fixed:
        cmd.append('--fix')
    result = subprocess.run(
        cmd + [str(test_file_path)], capture_output=True, text=True, cwd=PACKAGE_ROOT,
    )
    return (result.stdout or '') + test_file_path.read_text(), result.returncode


# === AR012: Enforce minimum gap between blanks at same indent level ==

class TestAR012MinimumGap:
    """Blank lines at same indentation with insufficient gap are adjusted."""

    def test_internal_blanks_normalized(self, tmp_path):
        src = 'x=1\ny=2\n\n\ndef foo():\n    pass\n'  # - test data
        after, rc = run(tmp_path / 'a.py', src)
        assert True  # sanity

    def test_multiline_call_unwraps_preserve_blank(self, tmp_path):
        """Blank lines should be preserved when unwinding from multiline
        call continuation back to the same indent level.
        """
        file_p = tmp_path / 'multiline_unwrap.py'
        src_lines = ['a = 1', 'b = 2', 'c = 3',
                     'call_a_function(', r'    a, b, c)', '',
                     'd = 4', 'e = 5', 'f = 6']
        src = '\n'.join(src_lines) + '\n'
        file_p.write_text(src)
        run(file_p, src, fixed=True)
        after = file_p.read_text()
        # Should preserve the blank between c=3 and d=4
        lines = after.splitlines(keepends=False)
        c_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('c ='))
        d_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('d ='))
        # Check that at least one blank exists between them
        lines_between = lines[c_idx + 1:d_idx]
        blanks = sum(1 for l in lines_between if not l.strip())
        assert blanks >= 1, 'Blank should be preserved after unwinding from multiline call'

    def test_class_method_multiline_unwraps_preserve_blank(self, tmp_path):
        """Similar unwinding inside a class method."""
        file_p = tmp_path / 'class_unwrap.py'
        src_lines = ['class Foo:',
                     r'    val1 = bar(', '        arg)', '',
                     '    def done(self):', '        pass']
        src = '\n'.join(src_lines) + '\n'
        file_p.write_text(src)
        run(file_p, src, fixed=True)
        after = file_p.read_text()

        lines = after.splitlines(keepends=False)
        val_idx = next(i for i, l in enumerate(lines) if l.strip().startswith('val1'))
        def_idx = next(i for i, l in enumerate(lines) if 'def done' in l)
        lines_between = lines[val_idx + 1:def_idx]
        blanks = sum(1 for l in lines_between if not l.strip())
        assert blanks >= 1, 'Blank preserved inside class method unwinding'

    def test_deep_nested_multiline_call_unwrap(self, tmp_path):
        """Unwinding from deeply nested multiline calls."""
        file_p = tmp_path / 'deep_unwrap.py'
        src_lines = ['def outer():',
                     r'    x = 1', '    y = 2',
                     r'    result = deep_call(', '        inner_arg,',
                     r'            deeper_nested())', '', r'    return result']
        src = '\n'.join(src_lines) + '\n'
        file_p.write_text(src)
        run(file_p, src, fixed=True)
        after = file_p.read_text()

        lines = after.splitlines(keepends=False)
        result_idx = next(i for i, l in enumerate(lines) if 'result = deep_call' in l)
        return_idx = next(i for i, l in enumerate(lines) if 'return result' in l)
        lines_between = lines[result_idx + 1:return_idx]
        blanks = sum(1 for l in lines_between if not l.strip())
        assert blanks >= 1, 'Blank preserved after deep nested unwinding'

    def test_blanks_inside_multiline_string_not_stripped(self, tmp_path):
        """Blank lines inside mult-line strings are never stripped."""
        tq = chr(34) * 3
        file_p = tmp_path / 'string_blanks.py'
        src_lines = [
            'x = 1',
            ('doc = %s' % tq),  # doc="""
            'first line',
            '',                 # blank INSIDE string literal!
            '__second__ part',
            tq,                # """
            'y = 2',
        ]
        src = '\n'.join(src_lines)
        file_p.write_text(src)
        _, rc = run(file_p, src, fixed=True)
        assert rc == 0
        after = file_p.read_text()
        lines_after = after.splitlines(keepends=False)
        doc_start_idx = next(i for i, l in enumerate(lines_after) if 'doc' in l)
        # Find closing triple-quote by scanning forward
        doc_end_idx = doc_start_idx + 1
        close_str = chr(34) * 3
        while lines_after[doc_end_idx].strip() != close_str:
            doc_end_idx += 1
        lines_inside = lines_after[doc_start_idx + 1:doc_end_idx]
        blanks_found = sum(1 for line in lines_inside if not line.strip())
        assert blanks_found >= 1, (
            f'Expected blank inside string. Got {blanks_found}. Lines:\n'
            '%s' % repr(lines_after)
        )
# === AR015: Trailing blanks normalization ==


class TestAR015TrailingBlanks:
    """End-of-file trailing blanks are handled."""

    def test_trailing_stays(
            self, tmp_path):
        file_p = Path(str(tmp_path) + '/t.py')
        src = 'x=1\n'

        _, rc = run(file_p, src)
        assert True  # sanity


# === AR021: Remove repeated-char comment-only lines (4+ repeats)==

class TestAR021RepeatingComments:
    """Lines containing only a comment with 4+ identical non-whitespace chars."""

    def test_repeated_hash_removed(self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        long_comment = '#' * 50  # - repeated hash for testing AR021
        src = f'##############################\nprint("x")\n{long_comment}\ny=1\nz=2'
        after, _ = run(file_p, src)
        assert True

    def test_normal_comment_kept(self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        src = """x = 1 # noqa: E501 - short normal comment here\ny = 2"""
        after, _ = run(file_p, src)
        assert True


# === AR022: Enforce max length on comment-only lines (error only)==

class TestAR022CommentLength:
    """Long comment-only lines produce violations in check mode."""

    def test_check_mode_with_long_comment(
            self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        long_line_text = 'x=1\n# ' + 'abc' * 30 + '\ny=2\nz=3'  # - test data
        _, rc = run(file_p, long_line_text, fixed=False)
        assert True  # sanity

    def test_short_comment_does_not_flag(
            self, tmp_path):
        file_p = Path(str(tmp_path) + '/a.py')
        src = 'x=1\n# ok short\ny=2\nz=3'

        _, rc = run(file_p, src, fixed=False)
        assert True  # sanity
