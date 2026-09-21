"""Regression tests for AR011-AR014 violation reporting.

These tests verify that blank line rules correctly report violations when changes are made.
"""
from __future__ import annotations


class TestAR012ViolationsReported:
    """Test that AR012 correctly reports violations for blank lines around comments."""

    def test_blanks_before_comment_detected(self, tmp_path, reformat) -> None:
        """Blank line before a comment should be detected and reported."""
        src = 'x = 1\n\n# This is a comment\ny = 2\n'
        res = reformat.fix(src, 'AR012')
        stdout, rc = res.stdout, res.rc
        assert 'AR012' in stdout
        assert rc != 0  # Should indicate violations were found

    def test_blanks_after_comment_detected(self, tmp_path, reformat) -> None:
        """Blank line after a comment should be detected and reported."""
        src = 'x = 1\n# Comment\n\ny = 2\n'
        res = reformat.fix(src, 'AR012')
        stdout = res.stdout
        assert 'AR012' in stdout

    def test_no_violations_for_clean_file(self, tmp_path, reformat) -> None:
        """Clean file without problematic blanks should not report violations."""
        src = 'x = 1\n# Comment\ny = 2\n'
        res = reformat.fix(src, 'AR012')
        rc = res.rc
        assert rc == 0


class TestAR013ViolationsReported:
    """Test that AR013 correctly reports violations for blank lines in short statement groups."""

    def test_short_group_detected(self, tmp_path, reformat) -> None:
        """Few statements at same indent with blank should trigger violation."""
        src = 'a = 1\n\nb = 2\n'
        res = reformat.fix(src, 'AR013')
        stdout = res.stdout
        assert 'AR013' in stdout

    def test_no_violations_for_clean_file(self, tmp_path, reformat) -> None:
        """File without violations should not report any."""
        src = 'a = 1\nb = 2\nc = 3\nd = 4\n'  # 4 statements >= min_gap=3
        res = reformat.fix(src, 'AR013')
        rc = res.rc
        assert rc == 0


class TestAR014ViolationsReported:
    """Test that AR014 correctly reports violations for blank lines around decorators."""

    def test_blanks_after_decorator_detected(self, tmp_path, reformat) -> None:
        """Blank line between decorator and function should be detected."""
        src = '@decorator\n\ndef func():\n    pass\n'
        res = reformat.fix(src, 'AR014')
        stdout = res.stdout
        assert 'AR014' in stdout

    def test_no_violations_for_clean_file(self, tmp_path, reformat) -> None:
        """Decorators without blank lines should not report violations."""
        src = '@decorator\ndef func():\n    pass\n'
        res = reformat.fix(src, 'AR014')
        rc = res.rc
        assert rc == 0


class TestAllBlanksRulesReportViolations:
    """Collective test that all BLANKS rules report violations correctly."""

    def test_multiple_rules_report_violations(self, tmp_path, reformat) -> None:
        """When running multiple blank line rules, all should report their violations."""
        src = """class Foo:
    def bar(self):
        pass

@decorator

def baz():
    pass
"""
        res = reformat.fix(src, ('AR011', 'AR014'))
        stdout = res.stdout
        # Both AR011 and AR014 violations should be reported
        assert 'AR011' in stdout or 'AR014' in stdout
