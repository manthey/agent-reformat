"""Tests for AR001: Strip single leading underscores from module-level variables."""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class TestAR001FixMode:
    """AR001 in fix mode should strip single leading underscores."""

    def test_var_with_noqa_is_preserved(self, tmp_path, reformat) -> None:
        """A variable with '# noqa: AR001' on its line must keep the underscore."""
        source = '_x = 1  # noqa: AR001\nprint(_x)\n'
        res = reformat.fix(source)
        after = res.after
        assert res.before == source, 'Original was mutated by helper'
        assert after == source, f'noqa-protected variable was changed:\n{after}'
        assert '_x' in after  # underscore must remain

    def test_var_used_and_no_noqa_is_stripped(self, tmp_path, reformat) -> None:
        """A variable with no noqa and used at least once should be stripped."""
        source = '_x = 1\nprint(_x)\n'
        after = reformat.fix(source).after
        assert after == 'x = 1\nprint(x)\n'

    def test_unused_var_is_preserved(self, tmp_path, reformat) -> None:
        """A variable that is only ever assigned never triggers AR001."""
        source = '_unused = 42\n'
        after = reformat.fix(source).after
        # Should not change because the variable is unused elsewhere.
        assert after == source


class TestAR001CheckMode:
    """AR001 in check (non-fix) mode should report violations via stdout."""

    def test_check_mode_no_file_change(self, tmp_path, reformat) -> None:
        """Check mode must never modify the source file."""
        source = '_x = 1\nprint(_x)\n'
        before = tmp_path / 'sample.py'
        before.write_text(source)
        res = reformat.check(source)
        rc = res.rc
        assert before.read_text() == source, 'Check mode must not modify the file'
        # Return code should be non-zero since AR001 violation detected.
        assert rc != 0

    def test_check_mode_output_contains_rule(self, tmp_path, reformat) -> None:
        """Stdout from check mode should mention AR001."""
        source = '_x = 1\nprint(_x)\n'
        stdout = reformat.check(source).stdout
        assert 'AR001' in stdout, f"Expected 'AR001' in:\n{stdout}"

    def test_no_violation_no_output(self, tmp_path, reformat) -> None:
        """A clean file should produce no violations (rc == 0)."""
        source = 'x = 1\nprint(x)\n'
        res = reformat.check(source)
        stdout, rc = res.stdout, res.rc
        assert rc == 0, f'Expected rc=0 but got {rc}\nstdout={stdout}'


class TestAR001NoqaProtection:
    """Verify that noqa directives correctly suppress AR001."""

    def test_bare_noqa_on_definition(self, tmp_path, reformat) -> None:
        """Bare '# noqa' on the definition line suppresses AR001."""
        source = '_x = 1  # noqa\nprint(_x)\n'
        after = reformat.fix(source).after
        assert after == source, 'bare noqa on def line should protect variable'

    def test_bracket_noqa_on_definition(self, tmp_path, reformat) -> None:
        """'# noqa: [AR001]' on the definition line suppresses AR001."""
        source = '_x = 1  # noqa: [AR001]\nprint(_x)\n'
        after = reformat.fix(source).after
        assert after == source

    def test_noqa_on_usage_line(self, tmp_path, reformat) -> None:
        """'# noqa' on the usage line should also protect."""
        source = '_x = 1\nprint(_x)  # noqa\n'
        after = reformat.fix(source).after
        assert after == source, 'noqa on usage line should protect variable'


class TestAR001EdgeCases:
    """Edge cases that should NOT trigger AR001."""

    def test_dunder_var_preserved(self, tmp_path, reformat) -> None:
        """Variables starting & ending with double underscore (__x__) keep their name."""
        source = "__version__ = '1.0'\nprint(__version__)\n"
        after = reformat.fix(source).after
        assert after == source

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        """Double-underscore prefix (not dunder) should not be stripped."""
        source = '__internal = 1\nprint(__internal)\n'
        after = reformat.fix(source).after
        assert after == source

    def test_ending_underscore_preserved(self, tmp_path, reformat) -> None:
        """Trailing underscore (e.g. classmethod 'cls') should not be stripped."""
        source = 'cls_ = 1\nprint(cls_)\n'
        after = reformat.fix(source).after
        assert after == source

    def test_single_usage_is_stripped(self, tmp_path, reformat) -> None:
        """Variable with exactly one reference should still be stripped."""
        source = '_data = 42\nprint(_data)\n'
        after = reformat.fix(source).after
        assert after == 'data = 42\nprint(data)\n'
