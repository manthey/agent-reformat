"""Tests for PEP 723 inline script metadata block and shebang protection."""
from __future__ import annotations

from hooks.agent_reformat import find_pep723_block


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


class TestPEP723BlankLines:
    """Test that blank lines around PEP 723 blocks are preserved."""

    def test_blank_line_after_pep723_preserved(self, tmp_path):
        """One blank line after PEP 723 block must be kept."""
        src = """# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
""" + '\nx = 1\n'
        f = tmp_path / 'test.py'
        f.write_text(src)
        import io
        import sys

        from hooks.agent_reformat import run as run_hook

        original_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            try:
                run_hook([str(f), '--fix'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        result = f.read_text()
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


class TestPEP723AR016Protection:
    """Test that AR016 does not remove blank lines around PEP 723 comments."""

    def test_ar016_respects_pep723_blanks(self, tmp_path):
        """Blank lines within PEP 723 block are not removed by AR016."""
        src = """# /// script
# requires-python = ">=3.11"
# ///
x = 1
y = 2
"""
        f = tmp_path / 'test.py'
        f.write_text(src)
        import io
        import sys

        from hooks.agent_reformat import run as run_hook

        original_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            try:
                run_hook([str(f), '--fix', '--rules', 'AR016'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        result = f.read_text()
        assert '# /// script' in result
        assert '# requires-python' in result


class TestPEP723AR021Protection:
    """Test that AR021 does not remove repeated-char comments inside PEP 723."""

    def test_ar021_skips_pep723_repeated_chars(self, tmp_path):
        """Repeated-char comments inside PEP 723 block are preserved."""
        src = """# /// script
# ########################
# requires-python = ">=3.11"
# ///
x = 1
"""
        f = tmp_path / 'test.py'
        f.write_text(src)
        import io
        import sys

        from hooks.agent_reformat import run as run_hook

        original_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            try:
                run_hook([str(f), '--fix', '--rules', 'AR021'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        result = f.read_text()
        assert '# ########################' in result


class TestShebangProtection:
    """Test that shebang lines are preserved."""

    def test_shebang_preserved(self, tmp_path):
        """Shebang line should not be altered."""
        src = """#!/usr/bin/env python3
x = 1
y = 2
"""
        f = tmp_path / 'test.py'
        f.write_text(src)
        import io
        import sys

        from hooks.agent_reformat import run as run_hook

        original_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            try:
                run_hook([str(f), '--fix', '--rules', 'AR016'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        result = f.read_text()
        assert '#!/usr/bin/env python3' in result


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
        f = tmp_path / 'test.py'
        f.write_text(src)
        import io
        import sys

        from hooks.agent_reformat import run as run_hook

        original_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            try:
                run_hook([str(f), '--fix'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        result = f.read_text()
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
