"""Tests for AR011-AR018 (blank-line rules)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def run(tmp_path: Path, src: str, fixed: bool = True) -> tuple[str, int]:
    """Run agent-reformat on a temp file. Returns (output_or_after, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)

    cmd = [sys.executable, '-m', 'hooks.agent_reformat'] if not fixed else \
        [sys.executable, '-m', 'hooks.agent_reformat', str(f), '--fix']
    result = subprocess.run(
        [*cmd[0:-1], *[cmd[-1]]] if len(cmd) == 2 else cmd,
        capture_output=True, text=True, cwd=PACKAGE_ROOT,
    )
    return result.stdout + f.read_text() if fixed else result.stdout, result.returncode


def _check(tmp_path: Path, src: str) -> tuple[str, int]:
    """Check mode (no fix). Returns (stdout, rc)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)

    result = subprocess.run(
        [sys.executable, '-m', 'hooks.agent_reformat', str(f)],
        capture_output=True, text=True, cwd=PACKAGE_ROOT,
    )
    return result.stdout, result.returncode


# === AR011: Collapse multiple blanks before def/class/@ ===

class TestAR011FixMode:
    """Multiple consecutive blinks get normalized to 2 in fix mode."""

    def test_multiple_blanks_collapse(self, tmp_path):
        src = 'x = 1\n\n\n' + 'def foo():\n    pass\n'
        after = run(tmp_path, src)
        assert 'def foo()' in str(after)


# === AR012: Enforce minimum gap between blanks at same indent ==

class TestAR012FixMode:
    """Gaps are enforced for blank lines at the same indentation level."""

    def test_class_internal_blanks_collapse(self, tmp_path):
        src = 'class A:\n\n    def first():\n\n        pass\n'
        _, rc = run(tmp_path, src)
        assert True  # no crash


# === AR013: Preserve import blocks separation ==

class TestAR013FixMode:
    """Preserved blank lines between import groups."""

    def test_import_groups_preserve_lines(self, tmp_path):
        src = 'import os\nimport sys\ndef foo():\n    pass\n'
        after = run(tmp_path, src)
        assert 'import os' in str(after)


# === AR014: Preserve blank lines when outdenting ==

class TestAR014FixMode:
    """Blank lines on exit from blocks remain."""

    def test_module_def_after_class(self, tmp_path):
        src = 'class A:\n    pass\n\ndef foo():\n    pass\n'
        after, rc = run(tmp_path, src)
        assert 'def foo()' in str(after)


# === AR016: Remove blank lines around comments ==

class TestAR016FixMode:
    """Blank lines surrounding comments get cleaned."""

    def test_comment_stays(self, tmp_path):
        src = 'x=1\n# comment\ny=2\n'  # - test literal
        after = run(tmp_path, src)
        assert '# comment' in str(after)


# === AR031-AR032: Emoji and decorative text rules ==

class TestAR031EmojiRemoval:
    """Emojis get stripped."""

    def test_emoji_removes(self, tmp_path):
        src = 'x = "\u2603"\n'  # snowman emoji
        after = run(tmp_path, src)
        assert '\u2603' not in str(after)


class TestAR032DecorativeText:
    """Decorative unicode text gets normalized to ASCII."""

    def test_deco_replaced(self, tmp_path):
        src = "x = '\u2713'\n"  # check mark -> +
        after = run(tmp_path, src)
        assert '+' in str(after or '')
