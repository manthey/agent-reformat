"""Tests for AR042: Non-exported function underscore stripping."""
from __future__ import annotations

import io
import sys
from pathlib import Path


def run_hook(tmp_path: Path, src: str) -> tuple[str, str]:
    """Run agent-reformat. Returns (prev_content, after_content)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)
    from hooks.agent_reformat import run
    err_output = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = err_output
        try:
            run([str(f), '--rules=AR042', '--fix'])
        except SystemExit:
            pass
    finally:
        sys.stdout = orig
    return src, f.read_text()


class TestNoAllDefined:
    """Without __all__, all functions are exported."""

    def test_non_exported_func_keeps_underline(self, tmp_path: Path) -> None:
        """Function keeps underscore when no __all__.__all__ means export."""
        src = '_helper(): pass\n_helper()\n'
        prev, result = run_hook(tmp_path, src)
        assert '_helper' in result

    def test_unused_func_not_stripped(self, tmp_path: Path) -> None:
        """Unused function not detected as needing stripping."""
        src = 'def _orphan():\n\n    pass\n'
        prev, result = run_hook(tmp_path, src)
        assert '_orphan' in result


class TestAllDefined:
    """Functions NOT in __all__ get their underscores stripped."""

    def test_non_exported_func_stripped(self, tmp_path: Path) -> None:
        """Function not in __all__ gets underscore stripped."""
        src = "__all__ = ['public']\ndef _work(): pass\n_work()\n"
        prev, result = run_hook(tmp_path, src)
        assert 'def work()' in result
        assert 'def _work()' not in result

    def test_exported_func_keeps_underline(self, tmp_path: Path) -> None:
        """Function in __all__ keeps its underscore."""
        src = "__all__ = ['_exposed']\n_exposed(): pass\n_exposed()\n"
        prev, result = run_hook(tmp_path, src)
        assert '_exposed' in result


class TestAsyncFunctions:
    """Async functions follow the same rules."""

    def test_async_non_exported_stripped(self, tmp_path: Path) -> None:
        """Async function not in __all__ has underscore stripped."""
        src = "__all__ = ['pub']\nasync def _fetch(): pass\n_fetch()\n"
        prev, result = run_hook(tmp_path, src)
        assert 'async def fetch()' in result


class TestNoqaProtection:
    """Verify noqa directive suppresses AR042."""

    def test_noqa_on_def_line(self, tmp_path: Path) -> None:
        """Bare # noqa on definition line protects underscore."""
        src = "__all__ = ['_p']\ndef _x():  # noqa\npass\n"
        prev, result = run_hook(tmp_path, src)
        assert '_x' in result

    def test_noqa_on_call_site(self, tmp_path: Path) -> None:
        """# noqa on usage site also protects."""
        src = "__all__ = ['p']\ndef _f(): pass\n_f()  # noqa\n"
        prev, result = run_hook(tmp_path, src)
        assert '_f' in result


class TestEdgeCases:
    """Names with certain patterns are exempt."""

    def test_dunder_func_preserved(self, tmp_path: Path) -> None:
        """Dunder functions never stripped."""
        src = 'def __version__():\n\n    pass\n'
        prev, result = run_hook(tmp_path, src)
        assert '__version__' in result

    def test_double_leading_underscore_preserved(self, tmp_path: Path) -> None:
        """Double-underscore functions always kept."""
        src = '__helper(): pass\n__helper()\n'
        prev, result = run_hook(tmp_path, src)
        assert '__helper' in result

    def test_trailing_underscore_preserved(self, tmp_path: Path) -> None:
        """Trailing underscore names never stripped."""
        src = 'cls_(): pass\nclass_()\n'
        prev, result = run_hook(tmp_path, src)
        assert 'cls_' in result


class TestStrictSubset:
    """AR042 strict subset AR002 behavior guarantees."""

    def test_no_all_strips_less_than_ar001(
        self, tmp_path: Path,
    ) -> None:
        """Without __all__, AR042 strips zero functions but
        AR001 would strip all.
        """
        src = '_g(): pass\n_g()\n'
        prev, result = run_hook(tmp_path, src)
        assert result == src  # No change under AR042

    def test_all_exported_names_kept(
        self, tmp_path: Path,
    ) -> None:
        """When export defined, keep names inside __all__."""
        src = "__all__ = ['_f']\n_f(): pass\n_f()\n"
        prev, result = run_hook(tmp_path, src)
        assert '_f' in result  # Not stripped
