"""Tests for AR041: Non-exported variable underscore stripping."""
from __future__ import annotations

import io
import sys
from pathlib import Path


def run_hook(tmp_path: Path, source: str) -> tuple[str, str]:
    """Run agent-reformat on a temp file. Returns (prev, after)."""
    f = tmp_path / 'sample.py'
    f.write_text(source)
    from hooks.agent_reformat import run
    out = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = out
        try:
            run([str(f), '--rules=AR041', '--fix'])
        except SystemExit:
            pass
    finally:
        sys.stdout = orig
    return source, f.read_text()


class TestNoAllExists:
    """Without __all__, all top-level names are exported."""

    def test_non_exported_var_keeps_underline(self, tmp_path: Path) -> None:
        """Var with leading underscore stays when no __all__ exists."""
        src = '_x = 1\nprint(_x)\n'
        prev, result = run_hook(tmp_path, src)
        assert result == src  # No changes

    def test_no_rule_violation_without_all(self, tmp_path: Path) -> None:
        src_file = tmp_path / 't.py'
        src_file.write_text('_x = 1\n_x()\n')
        out_buf = io.StringIO()
        from hooks.agent_reformat import run
        prev_out, sys.stdout = sys.stdout, out_buf
        try:
            try:
                run([str(src_file), '--rules=AR041'])  # No --fix (check mode)
            except SystemExit:
                pass
        finally:
            sys.stdout = prev_out
        out_str = out_buf.getvalue()
        assert 'AR041' not in out_str  # No AR041 violations without __all__


class TestAllDefined:
    """When __all__ defined, only listed names are protected."""

    def test_non_exported_var_stripped(self, tmp_path: Path) -> None:
        """Var NOT in __all__ has underscore stripped when used."""
        src = "__all__ = ['_priv']\n_x = 1\nprint(_x)\n"
        prev, result = run_hook(tmp_path, src)
        assert 'x = 1' in result
        assert '_x' not in result

    def test_exported_name_in_all_keeps_underline(self, tmp_path: Path) -> None:
        """Name listed in __all__ keeps its leading underscore."""
        src = "__all__ = ['_exposed']\n_exposed = 42\nprint(_exposed)\n"
        prev, result = run_hook(tmp_path, src)
        assert '_exposed' in result

    def test_var_not_in_export_list_is_stripped(
        self, tmp_path: Path,
    ) -> None:
        """Vars not in __all__ list get stripped even if others do."""
        src = "__all__ = ['_priv']\n_y = 2\n_x = 3\nprint(_x)\n"
        prev, result = run_hook(tmp_path, src)
        assert '_y' in result
        assert 'x = 3' in result


class TestNoqaProtection:
    """Verify noqa directive suppresses AR041."""

    def test_noqa_on_def_line(self, tmp_path: Path) -> None:
        """Bare # noqa on variable line protects from stripping."""
        src = "__all__ = ['_p']\n_x = 1  # noqa\nprint(_x)\n"
        prev, result = run_hook(tmp_path, src)
        assert '_x' in result

    def test_noqa_on_call_line(self, tmp_path: Path) -> None:
        """# noqa on usage line protects variable."""
        src = "__all__ = ['_p']\n_x = 1\nprint(_x)  # noqa\n"
        prev, result = run_hook(tmp_path, src)
        assert '_x' in result


class TestEdgeCases:
    """Patterns that are always exempt from stripping."""

    def test_dunder_var_preserved(self, tmp_path: Path) -> None:
        """Dunder names never stripped by AR041."""
        src = "__version__ = '1'\nprint(__version__)\n"
        prev, result = run_hook(tmp_path, src)
        assert '__version__' in result

    def test_double_leading_underscore_kept(self, tmp_path: Path) -> None:
        """Double-underscore prefix preserved."""
        src = "__pvt = 'val'\nprint(__pvt)\n"
        prev, result = run_hook(tmp_path, src)
        assert '__pvt' in result

    def test_ending_underscore_kept(self, tmp_path: Path) -> None:
        """Trailing underscore preserved (e.g. classmethod pattern)."""
        src = "foo_bar_ = 'x'\nprint(foo_bar_)\n"
        prev, result = run_hook(tmp_path, src)
        assert 'foo_bar_' in result


class TestStrictSubset:
    """AR041 must be strict subset of AR001 behavior."""

    def test_no_all_means_nothing_stripped(
        self, tmp_path: Path,
    ) -> None:
        """Without __all__, AR041 strips no variables.
        """
        src = '_x = 1\nprint(_x)\n'
        prev, result = run_hook(tmp_path, src)
        assert result == src

    def test_export_names_in_all_not_stripped(
        self, tmp_path: Path,
    ) -> None:
        """With __all__ containing a name, keep its underscore."""
        src = "__all__ = ['_foo']\n_foo = 1\nprint(_foo)\n"
        prev, result = run_hook(tmp_path, src)
        assert '_foo' in result
