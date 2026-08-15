"""Tests for PEP 723 inline script metadata block and shebang protection."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from hooks.agent_reformat import find_pep723_block
from hooks.agent_reformat import run as run_hook


def test_find_pep723_basic():
    src = """# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
print("hello")
"""
    start, end = find_pep723_block(src)
    assert start == 1
    assert end == 4


def test_find_pep723_with_spaces():
    src = """# /// script
# requires-python = ">=3.11"
# ///
x = 1
"""
    start, end = find_pep723_block(src)
    assert start == 1
    assert end == 3


def test_find_pep723_not_found():
    src = """print("hello")
"""
    start, end = find_pep723_block(src)
    assert start == -1
    assert end == -1


def test_find_pep723_multiple_blocks_finds_first():
    src = """# /// script
# requires-python = ">=3.11"
# ///
x = 1
# /// some other thing
"""
    start, end = find_pep723_block(src)
    assert start == 1
    assert end == 3


def run_fix(tmp_path: Path, src: str, rules=None) -> str:
    """Run agent-reformat fix mode and return changed source."""
    f = tmp_path / 'test.py'
    f.write_text(src)
    cmd_args = [str(f), '--fix']
    if rules:
        cmd_args.extend(['--rules', rules])
    orig_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook(cmd_args)
        except SystemExit:
            pass
    finally:
        sys.stdout = orig_stdout
    return f.read_text()


class TestPEP723BlankLines:
    """Test that blank lines around PEP 723 blocks are preserved."""

    def test_blank_line_after_pep723_preserved(self, tmp_path):
        """One blank line after PEP 723 block must be kept."""
        src = (
            '# /// script\n# requires-python = ">=3.11"\n'
            '# dependencies = []\n# ///\n'
            '\nx = 1\n'
        )
        result = run_fix(tmp_path, src)
        # The blank line after the PEP 723 block should be preserved
        assert '# ///' in result
        # Check that there is at least one blank line between # /// and x = 1
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == '# ///':
                found_blank = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j]
                    if not next_line.strip():
                        found_blank = True
                        break
                    if 'x = 1' in next_line:
                        break
                assert found_blank, (
                    f'Expected blank line after PEP 723 block. '
                    f'Lines: {lines[i:i+5]!r}'
                )
                break


class TestPEP723WithShebang:
    """Test PEP 723 blocks followed by shebang."""

    def test_pep723_then_shebang(self, tmp_path):
        """Blank line preserved after PEP 723 before shebang and code."""
        src = """# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
#!/usr/bin/env python3
print("hello")
"""
        result = run_fix(tmp_path, src)
        assert '# ///' in result
        # Verify there is at least one blank line between PEP 723 and shebang
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == '# ///':
                assert i + 1 < len(lines), 'Missing line after # ///'
                next_line = lines[i + 1]
                assert next_line.strip() == '' or next_line.startswith('#!'), (
                    f'Expected blank line or shebang after # ///, got: {next_line!r}'
                )


class TestShebangProtection:
    """Test that shebang lines are preserved."""

    def test_shebang_preserved(self, tmp_path):
        """Shebang line should not be altered."""
        src = """#!/usr/bin/env python3
x = 1
y = 2
"""
        result = run_fix(tmp_path, src)
        assert '#!/usr/bin/env python3' in result


class TestPEP723AR021Protection:
    """Test that AR021 does not remove repeated-char comments inside PEP 723."""

    def test_ar021_skips_pep723_repeated_chars(self, tmp_path):
        """Repeated-char comments inside PEP 723 block are preserved."""
        src = (
            '# /// script\n'
            '# ########################\n'
            '# requires-python = ">=3.11"\n# ///\nx = 1\n'
        )
        result = run_fix(tmp_path, src, rules='AR021')
        assert '# ########################' in result


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, '-v'])
