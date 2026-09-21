"""Tests for AR042: Non-exported function underscore stripping."""
from __future__ import annotations


class TestNoAllDefined:
    """Without __all__, all functions are exported."""

    def test_non_exported_func_keeps_underline(self, tmp_path, reformat) -> None:
        """Function keeps underscore when no __all__.__all__ means export."""
        src = '_helper(): pass\n_helper()\n'
        result = reformat.fix(src, 'AR042').after
        assert '_helper' in result

    def test_unused_func_not_stripped(self, tmp_path, reformat) -> None:
        """Unused function not detected as needing stripping."""
        src = 'def _orphan():\n\n    pass\n'
        result = reformat.fix(src, 'AR042').after
        assert '_orphan' in result


class TestAllDefined:
    """Functions NOT in __all__ get their underscores stripped."""

    def test_non_exported_func_stripped(self, tmp_path, reformat) -> None:
        """Function not in __all__ gets underscore stripped."""
        src = "__all__ = ['public']\ndef _work(): pass\n_work()\n"
        result = reformat.fix(src, 'AR042').after
        assert 'def work()' in result
        assert 'def _work()' not in result

    def test_exported_func_keeps_underline(self, tmp_path, reformat) -> None:
        """Function in __all__ keeps its underscore."""
        src = "__all__ = ['_exposed']\n_exposed(): pass\n_exposed()\n"
        result = reformat.fix(src, 'AR042').after
        assert '_exposed' in result


class TestAsyncFunctions:
    """Async functions follow the same rules."""

    def test_async_non_exported_stripped(self, tmp_path, reformat) -> None:
        """Async function not in __all__ has underscore stripped."""
        src = "__all__ = ['pub']\nasync def _fetch(): pass\n_fetch()\n"
        result = reformat.fix(src, 'AR042').after
        assert 'async def fetch()' in result


class TestNoqaProtection:
    """Verify noqa directive suppresses AR042."""

    def test_noqa_on_def_line(self, tmp_path, reformat) -> None:
        """Bare # noqa on definition line protects underscore."""
        src = "__all__ = ['_p']\ndef _x():  # noqa\npass\n"
        result = reformat.fix(src, 'AR042').after
        assert '_x' in result

    def test_noqa_on_call_site(self, tmp_path, reformat) -> None:
        """# noqa on usage site also protects."""
        src = "__all__ = ['p']\ndef _f(): pass\n_f()  # noqa\n"
        result = reformat.fix(src, 'AR042').after
        assert '_f' in result


class TestEdgeCases:
    """Names with certain patterns are exempt."""

    def test_dunder_func_preserved(self, tmp_path, reformat) -> None:
        """Dunder functions never stripped."""
        src = 'def __version__():\n\n    pass\n'
        result = reformat.fix(src, 'AR042').after
        assert '__version__' in result

    def test_double_leading_underscore_preserved(self, tmp_path, reformat) -> None:
        """Double-underscore functions always kept."""
        src = '__helper(): pass\n__helper()\n'
        result = reformat.fix(src, 'AR042').after
        assert '__helper' in result

    def test_trailing_underscore_preserved(self, tmp_path, reformat) -> None:
        """Trailing underscore names never stripped."""
        src = 'cls_(): pass\nclass_()\n'
        result = reformat.fix(src, 'AR042').after
        assert 'cls_' in result


class TestStrictSubset:
    """AR042 strict subset AR002 behavior guarantees."""

    def test_no_all_strips_less_than_ar001(self, tmp_path, reformat) -> None:
        """Without __all__, AR042 strips zero functions but
        AR001 would strip all.
        """
        src = '_g(): pass\n_g()\n'
        result = reformat.fix(src, 'AR042').after
        assert result == src  # No change under AR042

    def test_all_exported_names_kept(self, tmp_path, reformat) -> None:
        """When export defined, keep names inside __all__."""
        src = "__all__ = ['_f']\n_f(): pass\n_f()\n"
        result = reformat.fix(src, 'AR042').after
        assert '_f' in result  # Not stripped
