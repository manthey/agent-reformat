"""test_all_rules.py - every agent-reformat rule exercised in one messy block.

MESSY_SOURCE below is deliberately messy Python that triggers every rule group
(underscores, blanks, comments, emojis) in a single pass.  A test harness
writes it to a temp file, runs agent-reformat on it, confirms every expected
rule code fires, and spot-checks the key transformations.

NOTE: All emoji/deco characters in MESSY_SOURCE are stored as Python unicode
escape sequences so that agent-reformat's own AR031/AR032 rules do not
strip them from this test file when it is committed.  When Python evaluates
messy_source the escapes become real codepoints that agent-reformat will find
and clean in the temp output file.
"""
import io
import sys
from pathlib import Path

# MESSY_SOURCE - the full messy input that exercises every rule group
from hooks.agent_reformat import run as agent_reformat_run

MESSY_SOURCE = """
# =============================================================================
#  AR001 / AR041   module-level variable underscores
# =============================================================================
_unexported_var = 1     # noqa: AR001 -> kept (noqa on def line)
_private_var = 3        # used below and no noqa -> stripped
_unused_var = 99        # never loaded -> untouched

# Edge cases that must always be preserved (never stripped):
__magic__ = True                # dunder
__internal_state = 10           # double-underscore prefix
foo_bar_ = 'trailing'           # trailing underscore


# =============================================================================
#  AR002 / AR042   top-level function underscores
# =============================================================================
def _unexported_fn():
    return _private_var          # ensures _private_var is loaded (not orphaned)


def _inner_fn():
    pass
_inner_fn()                      # bare Name usage -> triggers 002 stripping


def __version__():               # dunder -> kept
    pass


def __helper():                  # double-underscore -> kept
    pass


def cls_():                      # trailing -> kept
    pass


def _orphan_fn():                # never loaded -> kept
    pass


# =============================================================================
#  AR003 / AR043   class method underscores
# =============================================================================
class PubClass:
    def __init__(self):          # dunder -> kept
        pass
    def __helper(self):          # double-underscore -> kept
        pass
    def cls_(self):              # trailing -> kept
        pass
    def _method(self):           # single leading _ -> AR003 strips it
        return 42

_method()                        # module-level bare Name -> triggers 003 stripping


# =============================================================================
#  AR004 / AR044   nested function underscores
# =============================================================================
class PubClass2:
    def method(self):
        def _nested_in_class():    # inside class method, used -> stripped
            pass
        _nested_in_class()


def outer_fn():
    def _nested_in_fn():           # inside top-level fn, used -> stripped
        pass
    _nested_in_fn()
    return _nested_in_fn


# =============================================================================
#  AR011   blank lines at indent/outdent transitions
#  (AR011 is string-safe: it skips multi-line string interiors, so these
#   patterns are safe to keep inside MESSY_SOURCE.)
# =============================================================================
def ar011_entry():


    return 1


if True:


    x = 1


# =============================================================================
#  AR012   blank lines immediately before/after standalone comments
# =============================================================================
# standalone comment line


def ar012_fn():
    a = 1


    b = 2


c = 3


class Ar012Class:
    def method(self):
        m = 1


        # comment inside class body


        n = 2


# =============================================================================
#  AR013   short statement groups lose internal blank  (min_gap=3 default)
# =============================================================================
p = 1
q = 2


# =============================================================================
#  AR014   blanks between decorators and their target
# =============================================================================
@dec1

@dec2


@dec3
def ar014_fn():
    return True


class Ar014Class:
    @classmethod

    def factory(cls):
        return cls()

    @property

    def value(self):
        return 1


# =============================================================================
#  AR021   repeating-char comment lines  (4+ identical non-ws chars)
# =============================================================================
##########


# =============================================================================
#  AR022   long comment-only lines  (check-only, no auto-fix)
# =============================================================================
# This AR022 demo comment is deliberately long enough to exceed the 79 char threshold.


# =============================================================================
#  AR031   genuine emoji removal
# =============================================================================
emoji_comment = True    # \U0001F600   supplementary-plane emoji -> removed
emoji_string = '\U0001F4A9'              # supplementary-plane emoji -> removed


# =============================================================================
#  AR032   decorative text replacement
# =============================================================================
deco = 'ok \u2713 fail \u2717 dead \u2718'       # deco marks -> replaced
not_emoji = 'cafe \u00e9   OK'                     # normal unicode -> kept


# =============================================================================
#  noqa protection   (names that must NOT be stripped)
# =============================================================================
_noqa_var = 1          # noqa: AR001


def _noqa_fn():        # noqa: AR002
    pass


def outer_protected():
    def _noqa_nested():   # noqa: AR004
        pass
    _noqa_nested()
"""   # END MESSY_SOURCE


def run(tmp_path: Path):
    """Write MESSY_SOURCE to a temp file and run agent-reformat --fix on it.

    Returns (cleaned_source_text, violation_lines_str).
    """
    src_file = tmp_path / 'messy.py'
    src_file.write_text(MESSY_SOURCE, encoding='utf-8')

    captured = io.StringIO()
    original = sys.stdout
    try:
        sys.stdout = captured
        try:
            agent_reformat_run([
                str(src_file),
                '--rules', 'AR',
                '--fix',
            ])
        except SystemExit:
            pass
    finally:
        sys.stdout = original

    return src_file.read_text(encoding='utf-8'), captured.getvalue()
#  Test 1: every expected rule code must fire at least once


class TestAllRulesFire:
    EXPECTED = frozenset({
        'AR001', 'AR002', 'AR003', 'AR004',
        'AR011', 'AR012', 'AR013', 'AR014',
        'AR021', 'AR031', 'AR032',
    })

    def test_every_rule_fires(self, tmp_path):
        _, violations = run(tmp_path)
        fired = {code for code in self.EXPECTED if code in violations}
        missing = self.EXPECTED - fired
        assert not missing, (
            'Missing rule violations: {}\nViolations seen:\n{}'.format(
                sorted(missing), violations,
            )
        )


class TestSpotChecks:
    def clean(self, tmp_path):
        return run(tmp_path)[0]

    def test_001_stripped(self, tmp_path):
        out = self.clean(tmp_path)
        msg = 'AR001: _private_var should become private_var'
        assert 'private_var = 3' in out, msg

    def test_001_unused_kept(self, tmp_path):
        out = self.clean(tmp_path)
        msg = '_unused_var must stay (never loaded)'
        assert '_unused_var = 99' in out, msg

    def test_dunder_kept(self, tmp_path):
        out = self.clean(tmp_path)
        assert '__magic__ = True' in out

    def test_double_underscore_kept(self, tmp_path):
        out = self.clean(tmp_path)
        assert '__internal_state = 10' in out

    def test_trailing_underscore_kept(self, tmp_path):
        out = self.clean(tmp_path)
        assert 'foo_bar_ =' in out

    def test_002_stripped(self, tmp_path):
        out = self.clean(tmp_path)
        assert 'def inner_fn()' in out, 'AR002: _inner_fn -> inner_fn'

    def test_003_stripped(self, tmp_path):
        out = self.clean(tmp_path)
        assert 'def method(self)' in out, 'AR003: _method -> method'

    def test_004_stripped(self, tmp_path):
        out = self.clean(tmp_path)
        assert 'def nested_in_class()' in out, 'AR004 nested_in_class'
        assert 'def nested_in_fn()' in out, 'AR004 nested_in_fn'

    def test_011_entry_blank_removed(self, tmp_path):
        out = self.clean(tmp_path)
        # The blank lines after the entry colon must be removed; the body kept
        msg = 'AR011: entry blanks for ``def ar011_entry():`` should be gone'
        assert 'def ar011_entry():\n    return 1' in out, msg

    def test_noqa_var_kept(self, tmp_path):
        out = self.clean(tmp_path)
        assert '_noqa_var = 1' in out, 'noqa-protected var must stay'

    def test_noqa_fn_kept(self, tmp_path):
        out = self.clean(tmp_path)
        assert 'def _noqa_fn()' in out, 'noqa-protected fn must stay'

    def test_ar031_emoji_removed(self, tmp_path):
        out = self.clean(tmp_path)
        # The supplementary-plane emoji U+1F600 must be gone
        assert chr(0x1F600) not in out, 'AR031: U+1F600 should be removed'

    def test_ar032_deco_replaced(self, tmp_path):
        out = self.clean(tmp_path)
        # U+2713 (checkmark) should have been replaced by AR032
        assert chr(0x2713) not in out, 'AR032: U+2713 should be replaced'

    def test_ar021_hash_line_removed(self, tmp_path):
        out = self.clean(tmp_path)
        assert '##########' not in out, 'AR021: ########## line must be removed'

    def test_non_emoji_preserved(self, tmp_path):
        out = self.clean(tmp_path)
        # U+00E9 (e-acute) is NOT an emoji and must remain
        assert chr(0x00E9) in out, 'non-emoji U+00E9 should be preserved'
