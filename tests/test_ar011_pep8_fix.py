"""
Tests to verify the AR011/blank line fix - ensuring no false positives for
PEP8-compliant files.
"""
import shutil
import sys
from pathlib import Path

from hooks.agent_reformat import fix_blanks

sys.path.insert(0, '/home/ubuntu/agent-reformat')


def test_two_blanks_before_pep8_def_no_violation():
    """
    PEP8 requires exactly 2 blanks before top-level def/class. This should NOT
    be a violation.
    """
    source = """\
def foo():
    pass


def bar():
    pass
"""
    tmpfile = Path('/tmp/test_tow_blanks.py')
    tmpfile.write_text(source)
    result = fix_blanks(str(tmpfile), {'AR011'}, min_gap=3, dry_run=True)

    assert result == [], (
        f'PEP8-compliant 2-blank lines should have no violations. Got: {result}'
    )


def test_three_blanks_should_have_violation():
    """More than 2 blanks before def should report exactly 1 violation for the excess."""
    source = """\
def foo():
    pass



def bar():
    pass"""
    tmpfile = Path('/tmp/test_threethree.py')
    tmpfile.write_text(source)
    result = fix_blanks(str(tmpfile), {'AR011'}, min_gap=3, dry_run=False)
    # Should report exactly 1 violation (for the extra blank line being
    # removed)
    assert len(result) == 1, f'Expected 1 violation for excess blank, got {len(result)}: {result}'
    # Verify the file was actually fixed - should now have exactly 2 blanks
    modified_source = tmpfile.read_text()
    assert source != modified_source, 'File should have been modified by fix_blanks'
    assert '\n\nd' in modified_source or '\n\n    pass\n\ndef' in modified_source, \
        f'Expected collapsed to 2 blanks but got:\n{modified_source}'


def test_single_blank_not_a_violation():
    """Single blank line is not a violation for AR011."""
    source = """\
def foo():
    pass

def bar():
    pass"""
    tmpfile = Path('/tmp/test_onetow.py')
    tmpfile.write_text(source)
    result = fix_blanks(str(tmpfile), {'AR011'}, min_gap=3, dry_run=True)
    assert result == [], f'Single blank should not be a violation. Got: {result}'


def test_pep723_block_preserved():
    """Blank lines after PEP 723 block should be preserved."""
    source = """\
# /// script
# dependencies = ["requests"]
# ///

import requests


def main():
    pass"""
    tmpfile = Path('/tmp/test_pep723.py')
    tmpfile.write_text(source)
    fix_blanks(str(tmpfile), {'AR011', 'AR015'}, min_gap=3, dry_run=False)
    # File should be unchanged since 2 blanks after PEP723 is correct format
    modified = tmpfile.read_text()
    assert source == modified, f'PEP723 block area was incorrectly changed:\n{modified}'


def test_rules_py_no_false_violations():
    """The actual rules.py file should not produce false violations."""
    rules_path = Path('/home/ubuntu/agent-reformat/hooks/rules.py')
    with open(rules_path) as f:
        source = f.read()
    tmpfile = Path('/tmp/test_rules_ar011.py')

    shutil.copy2(str(rules_path), str(tmpfile))
    result_dry = fix_blanks(str(tmpfile), {'AR011'}, min_gap=3, dry_run=True)
    # Check for false positives - violations at def/class lines preceded by
    # exactly 2 blanks
    rules_lines = source.split('\n')
    for lineno, _code in result_dry:
        if lineno <= len(rules_lines):
            line_text = rules_lines[lineno - 1]
            # Count blanks BEFORE this line going backward
            prior_blanks = 0
            for i in range(max(0, lineno - 2), max(0, lineno - 5), -1):
                if not rules_lines[i]:
                    prior_blanks += 1
                else:
                    break
            # If there are exactly 2 blanks before a def/class line
            # FALSE POSITIVE
            if prior_blanks == 2 and (line_text.startswith(('def ', 'class '))):
                msg = (
                    f'FALSE VIOLATION at line {lineno} (before PEP8-compliant def/class):\n'
                    f'  Line {lineno}: {repr(line_text[:50])}\n'
                    f'  Preceded by exactly 2 blank lines which are PEP8-correct\n'
                    f'  Total violations reported: {len(result_dry)}'
                )
                raise AssertionError(
                    msg,
                )
    print(f'+ rules.py test passed - {len(result_dry)} violations (none false positives)')


def test_dry_vs_fix_consistency():
    """Dry-run and fix mode should report the same violations for consistent behavior."""
    source = """\
a = 1



def foo():
    pass"""
    tmpfile_dry = Path('/tmp/test_compare_dry.py')
    tmpfile_fix = Path('/tmp/test_compare_fix.py')
    tmpfile_dry.write_text(source)
    tmpfile_fix.write_text(source)
    result_dry = fix_blanks(str(tmpfile_dry), {'AR011'}, min_gap=3, dry_run=True)
    result_fix = fix_blanks(str(tmpfile_fix), {'AR011'}, min_gap=3, dry_run=False)

    assert len(result_dry) == len(result_fix), (
        f'Dry and fix mode inconsistent: '
        f'dry={len(result_dry)} violations, fix={len(result_fix)} violations'
    )
    print(f'+ Dry/fix consistency test passed ({len(result_fix)} violations)')


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
