"""Tests for AR031 (remove emoji characters) and its AR032 interaction.

AR031 removes emoji characters from Python source files.
AR032 replaces decorative text (ballot check/X marks) with plain ASCII.

Emoji literals are spelled with unicode escapes in this file on purpose:
the repo's own pre-commit hook runs agent-reformat (AR031), which would
strip literal emoji from committed Python sources.
"""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from hooks.agent_reformat import has_genuine_emoji, is_emoji_char
from hooks.agent_reformat import run as run_hook


def run_rule(
    tmp_path: Path,
    source_code: str,
    rules: str,
    fix_mode: bool = False,
) -> tuple[int, str, str]:
    """Run the hook on a temp file with the given rules.

    Returns (exit_code, stdout_text, file_contents_after).
    """
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    args = [str(f), '--rules', rules]
    if fix_mode:
        args.append('--fix')
    original_stdout = sys.stdout
    captured = StringIO()
    rc = 0
    try:
        sys.stdout = captured
        try:
            run_hook(args)
        except SystemExit as exc:
            rc = exc.code if exc.code is not None else 0
    finally:
        sys.stdout = original_stdout
    return rc, captured.getvalue(), f.read_text()


class TestIsEmojiChar:
    """Classification of individual characters by is_emoji_char()."""

    def test_supplementary_plane_emoji(self) -> None:
        for ch in ('\U0001F600', '\U0001F389', '\U0001F4A9', '\U0001FA90'):
            assert is_emoji_char(ch) is True, f'U+{ord(ch):04X} should be emoji'

    def test_games_and_playing_card_emoji(self) -> None:
        for ch in ('\U0001F004', '\U0001F0CF'):
            assert is_emoji_char(ch) is True, f'U+{ord(ch):04X} should be emoji'

    def test_bmp_emoji(self) -> None:
        for ch in ('\u2600', '\u2705', '\u2192', '\u2022', '\u2588', '\u2764'):
            assert is_emoji_char(ch) is True, f'U+{ord(ch):04X} should be emoji'

    def test_decorative_ballot_marks_are_not_emoji(self) -> None:
        """AR032 replacement targets are not counted as genuine emoji."""
        for ch in ('\u2713', '\u2717', '\u2718'):
            assert is_emoji_char(ch) is False, f'U+{ord(ch):04X} is AR032 deco'

    def test_regional_indicators_are_not_in_emoji_set(self) -> None:
        """Flag sequences (regional indicators) are not in the emoji ranges."""
        for ch in ('\U0001F1FA', '\U0001F1F8'):
            assert is_emoji_char(ch) is False, f'U+{ord(ch):04X} outside ranges'

    def test_plain_and_general_unicode_is_not_emoji(self) -> None:
        for ch in ('a', '#', ' ', '\u00E9', '\u00B0', '\u4E2D', '\u2013'):
            assert is_emoji_char(ch) is False, f'U+{ord(ch):04X} must stay'


class TestHasGenuineEmoji:
    """Line-level genuine-emoji detection (the AR031 violation condition)."""

    def test_lines_with_genuine_emoji(self) -> None:
        assert has_genuine_emoji('# note \U0001F600') is True
        assert has_genuine_emoji('s = "x\u2705"') is True
        assert has_genuine_emoji('\u2600 alone') is True

    def test_decorative_only_lines(self) -> None:
        assert has_genuine_emoji('# \u2713 done') is False
        assert has_genuine_emoji('\u2717 and \u2718 marks') is False

    def test_plain_lines(self) -> None:
        assert has_genuine_emoji('x = 1') is False
        assert has_genuine_emoji('caf\u00E9, \u00B0C, \u2013 dash') is False
        assert has_genuine_emoji('') is False


class TestAR031Removal:
    """AR031 --fix must strip emoji characters and report violations."""

    def test_emoji_in_comment_removed(self, tmp_path: Path) -> None:
        src = 'x = 1  # happy \U0001F600\ny = 2\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert 'AR031' in out
        assert '\U0001F600' not in after
        assert after == 'x = 1  # happy \ny = 2\n'

    def test_emoji_in_string_removed(self, tmp_path: Path) -> None:
        src = 's = "party \U0001F389"\nprint(s)\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 's = "party "\nprint(s)\n'

    def test_emoji_in_docstring_removed(self, tmp_path: Path) -> None:
        src = 'def f():\n    """Doc \U0001F4A9 end."""\n    return 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 'def f():\n    """Doc  end."""\n    return 1\n'

    def test_multiple_emoji_on_one_line(self, tmp_path: Path) -> None:
        src = 's = "\U0001F600\U0001F389"\nprint(s)\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 's = ""\nprint(s)\n'

    def test_bmp_emoji_removed(self, tmp_path: Path) -> None:
        src = 'x = 1  # \u2600\u2764\u2192\ny = 2\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 'x = 1  # \ny = 2\n'

    def test_bullet_and_block_removed(self, tmp_path: Path) -> None:
        src = 'x = 1  # \u2022 \u2588\ny = 2\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 'x = 1  #  \ny = 2\n'

    def test_variation_selector_removed(self, tmp_path: Path) -> None:
        src = 's = "go \uFE0F now"\nprint(s)\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert after == 's = "go  now"\nprint(s)\n'

    def test_non_emoji_unicode_preserved(self, tmp_path: Path) -> None:
        src = 's = "\u00E9 \u00B0 \u4E2D\u6587 \u2013 \u20AC 5"\nprint(s)\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 0
        assert 'AR031' not in out
        assert after == src

    def test_regional_indicators_preserved(self, tmp_path: Path) -> None:
        """Regional indicators are not in the AR031 emoji ranges."""
        src = 's = "\U0001F1FA\U0001F1F8"\nprint(s)\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 0
        assert 'AR031' not in out
        assert after == src


class TestAR031CheckMode:
    """Without --fix the file is untouched but violations are reported."""

    def test_check_mode_reports_and_leaves_file(self, tmp_path: Path) -> None:
        target = tmp_path / 'test.py'
        src = 'x = 1\n# \U0001F600\ny = 2\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031')
        assert rc == 1
        assert after == src
        assert f'{target}:2: AR031 (emojis)' in out

    def test_clean_file_check_mode_no_changes(self, tmp_path: Path) -> None:
        src = 'x = 1\n# just a comment\ny = 2\nz = 3\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031')
        assert rc == 0
        assert 'AR031' not in out
        assert after == src

    def test_multiple_emoji_lines_all_reported(self, tmp_path: Path) -> None:
        src = '# a \U0001F600\n# b \U0001F389\nx = 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031')
        assert rc == 1
        assert after == src
        assert out.count('AR031 (emojis)') >= 2


class TestAR031VsAR032:
    """Each rule mutates only its own part and reports only itself.

    AR031 removes genuine emoji; AR032 replaces decorative ballot marks.
    Requesting one rule must not silently apply the other's fix.
    """

    def test_decorative_only_untouched_by_ar031(self, tmp_path: Path) -> None:
        """AR032 replacements must not run when only AR031 is requested."""
        src = '# \u2713 pass, \u2717 fail, \u2718 dead\nx = 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 0
        assert 'AR031' not in out
        assert after == src

    def test_ar031_keeps_decorative_marks(self, tmp_path: Path) -> None:
        """AR031 alone strips the emoji but leaves the deco mark alone."""
        src = '# \u2713 done \U0001F600\nx = 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031', fix_mode=True)
        assert rc == 1
        assert 'AR031' in out
        assert 'AR032' not in out
        assert after == '# \u2713 done \nx = 1\n'

    def test_ar032_alone_keeps_emoji(self, tmp_path: Path) -> None:
        """AR032 alone replaces the deco mark but preserves genuine emoji."""
        target = tmp_path / 'test.py'
        src = '# \u2713 done \U0001F600\nx = 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR032', fix_mode=True)
        assert rc == 1
        assert f'{target}:1: AR032 (emojis)' in out
        assert 'AR031' not in out
        assert after == '# + done \U0001F600\nx = 1\n'

    def test_mixed_line_reports_both_rules(self, tmp_path: Path) -> None:
        target = tmp_path / 'test.py'
        src = '# \u2713 done \U0001F600\nx = 1\n'
        rc, out, after = run_rule(tmp_path, src, 'AR031,AR032', fix_mode=True)
        assert rc == 1
        assert f'{target}:1: AR031 (emojis)' in out
        assert f'{target}:1: AR032 (emojis)' in out
        assert after == '# + done \nx = 1\n'
