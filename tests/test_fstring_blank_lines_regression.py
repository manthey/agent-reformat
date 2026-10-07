"""Regression test: blank lines inside f-strings must never be removed.

On Python 3.12+ f-strings tokenize as ``FSTRING_START`` /
``FSTRING_MIDDLE`` / ``FSTRING_END`` rather than a single ``STRING`` token.
``find_string_lines`` only recognised ``STRING``, so f-string interiors were
not protected and the blank-line rules (AR011-AR014) deleted blank lines
that are actually string content, changing program behaviour.

These tests cover plain multi-line strings, f-strings, and nested f-strings
for every blank-line rule.
"""
from __future__ import annotations

import tokenize

import pytest

# A multi-line f-string with blank lines that are part of its value, plus a
# second top-level statement so AR013 has a short group to (not) collapse.
FSTRING_SRC = '''def build(name):
    prompt = f"""
    First paragraph about {name}.

    Second paragraph.

    Third paragraph.
    """
    return prompt


def other():
    return 1
'''
# A nested multiline f-string inside a replacement field.
NESTED_SRC = 'x = f"""\na{f"""i\n\nz"""}\n\nb\n"""\n'
# A template string (PEP 750) with interior blank lines; only valid syntax
# on Python 3.14+.
TSTRING_SRC = 'x = t"""\na{y}\n\nb\n"""\n'
needs_tstrings = pytest.mark.skipif(
    not hasattr(tokenize, 'TSTRING_START'),
    reason='template strings (PEP 750) require Python 3.14+',
)


class TestFStringBlankLines:
    """Interior blank lines of f-strings survive every blank-line rule."""

    @pytest.mark.parametrize('rule', ['AR011', 'AR012', 'AR013', 'AR014'])
    def test_fstring_interior_blanks_survive(self, reformat, rule) -> None:
        """AR011-AR014 must leave a multi-line f-string byte-for-byte intact."""
        res = reformat.fix(FSTRING_SRC, rule)
        assert res.after == res.before, (
            f'{rule} modified blank lines inside an f-string:\n{res.after}'
        )

    @pytest.mark.parametrize('rule', ['AR011', 'AR012', 'AR013', 'AR014'])
    def test_nested_fstring_interior_blanks_survive(self, reformat, rule) -> None:
        """Nested f-strings (in replacement fields) are protected too."""
        res = reformat.fix(NESTED_SRC, rule)
        assert res.after == res.before, (
            f'{rule} modified blank lines inside a nested f-string:\n{res.after}'
        )

    @pytest.mark.parametrize('rule', ['AR011', 'AR012', 'AR013', 'AR014'])
    def test_plain_multiline_string_still_protected(self, reformat, rule) -> None:
        """The pre-existing plain-string behaviour is unchanged."""
        src = 'x = """\na\n\nb\n"""\n'
        res = reformat.fix(src, rule)
        assert res.after == res.before

    def test_reported_reproduction_unchanged(self, reformat) -> None:
        """The exact reproduction from the bug report is left unchanged."""
        res = reformat.fix(FSTRING_SRC, 'AR013')
        assert res.after == FSTRING_SRC
        assert res.stdout.count('AR013') == 0

    def test_real_blank_outside_fstring_still_removed(self, reformat) -> None:
        """String awareness did not disable the rule for real blanks."""
        src = 'def foo():\n\n    x = f"""a\n\nb"""\n    return x\n'
        after = reformat.fix(src, 'AR011').after
        assert after == 'def foo():\n    x = f"""a\n\nb"""\n    return x\n'

    @needs_tstrings
    @pytest.mark.parametrize('rule', ['AR011', 'AR012', 'AR013', 'AR014'])
    def test_tstring_interior_blanks_survive(self, reformat, rule) -> None:
        """Template strings (PEP 750) are protected like f-strings."""
        res = reformat.fix(TSTRING_SRC, rule)
        assert res.after == res.before, (
            f'{rule} modified blank lines inside a t-string:\n{res.after}'
        )


class TestMultilineStringStatementCounted:
    """A statement whose own RHS is a multi-line string is still a statement.

    The interior blank lines must be protected, but the assignment itself
    must be counted when AR013 groups consecutive statements at one indent.
    """

    @pytest.mark.parametrize(
        'quote',
        ['"""', 'f"""', 't"""'],
        ids=['plain', 'fstring', 'tstring'],
    )
    def test_assignment_with_multiline_string_is_a_statement(
        self, reformat, quote,
    ) -> None:
        if quote == 't"""' and not hasattr(tokenize, 'TSTRING_START'):
            pytest.skip('template strings (PEP 750) require Python 3.14+')
        src = (
            'def foo():\n'
            f'    x = {quote}\n'
            '    a\n'
            '\n'
            '    b\n'
            f'    {quote}\n'
            '    return x\n'
        )
        after = reformat.fix(src, 'AR013').after
        # The assignment plus ``return`` form a short group; the blank line
        # inside the string must survive while the string stays intact.
        assert '    a\n\n    b' in after, f'string interior was mutated:\n{after}'

    def test_blank_after_multiline_string_statement_removed(self, reformat) -> None:
        """The assignment counts, so a following short group collapses."""
        src = (
            'def foo():\n'
            '    x = """\n'
            '    a\n'
            '\n'
            '    b\n'
            '    """\n'
            '\n'
            '    return x\n'
        )
        after = reformat.fix(src, 'AR013').after
        # Interior blank preserved, structural blank between the two
        # statements (short group) removed.
        assert '    a\n\n    b' in after
        assert '"""\n    return x' in after
