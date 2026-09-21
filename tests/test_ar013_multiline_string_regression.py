"""Regression test for AR013 bug: blank lines inside multi-line strings removed.

AR013 must never remove lines that are merely blank *within* a multi-line
string literal.  The bug appeared when the statements on either side of the
string were more than two lines away from the string token (so they were not
skipped by the statement-collection heuristic) and formed a short group: the
blank line inside the string was then treated as a gap between the two
statements and deleted, corrupting the string content.
"""
from __future__ import annotations


class TestAR013MultilineStringRegression:
    """Blank lines inside multi-line strings survive AR013."""

    def test_blank_inside_string_preserved_distant_statements(self, tmp_path, reformat) -> None:
        """Blank inside a multi-line string is preserved even though the
        surrounding statements form a short group (< min_gap).

        The spacer comments/blank lines keep both statements more than two
        lines from the string token, which is what previously let the blank
        inside the string be misidentified as a removable group gap.
        """
        src = '''a = 1
# spacer comment 1
# spacer comment 2
x = """
hello

world
"""


y = 1
'''
        after = reformat.fix(src, 'AR013').after
        # The blank line inside the string must remain
        assert 'hello\n\nworld' in after
        # The genuine blanks between the string and the next statement
        # (short group, < min_gap) are still removed by AR013
        assert '"""\ny = 1' in after

    def test_blank_inside_string_inside_function_preserved(self, tmp_path, reformat) -> None:
        """Same guarantee holds for a function-local multi-line string."""
        src = '''def foo():
    a = 1
    # spacer comment 1
    # spacer comment 2
    x = """
    hello

    world
    """


    y = 1
'''
        after = reformat.fix(src, 'AR013').after
        assert 'hello\n\n    world' in after
        assert '"""\n\n\n    y = 1' in after or '"""\n    y = 1' in after
