"""Tests for AR043: Method underscore stripping in non-exported classes."""
from __future__ import annotations

import io
import sys
from pathlib import Path


def run_hook(tmp_path: Path, src: str) -> tuple[str, str]:
    """Run agent-reformat. Returns (prev_content, after)."""
    f = tmp_path / 'sample.py'
    f.write_text(src)
    from hooks.agent_reformat import run
    err_output = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = err_output
        try:
            run([str(f), '--rules=AR043', '--fix'])
        except SystemExit:
            pass
    finally:
        sys.stdout = orig
    return src, f.read_text()


class TestPublicClassMethods:
    """Methods in exported classes keep underscores."""

    def test_public_class_method_kept_with_all(self, tmp_path: Path) -> None:
        """Class listed in __all__ has protected methods."""
        src = "__all__ = ['MyClass']\nclass MyClass:\n\t" \
              'def _helper(): pass\n'
        prev, result = run_hook(tmp_path, src)
        assert '_helper' in result  # Kept because public class


class TestNonPublicClassMethods:
    """Methods in private classes can have underscores stripped."""

    def test_private_class_method_kept_no_all(
        self, tmp_path: Path,
    ) -> None:
        """An underscore-named class is non-exported, so its methods strip."""
        src = (
            'class _Helper:\n'
            '    def _impl(self):\n'
            '        pass\n'
            'h = _Helper()\n'
            'h._impl()\n'
        )
        prev, result = run_hook(tmp_path, src)
        assert 'def impl(self):' in result
        assert '_impl' not in result


class TestNoAll:
    """Without __all__, behavior differs by prefix name."""

    def test_public_class_keeps_methods(self, tmp_path: Path) -> None:
        """Without __all__, a public class keeps its method underscores."""
        src = (
            'class PublicClass:\n'
            '    def _helper(self):\n'
            '        pass\n'
            'p = PublicClass()\n'
            'p._helper()\n'
        )
        prev, result = run_hook(tmp_path, src)
        assert result == src
        assert '_helper' in result


class TestAsyncMethods:
    """Async methods respect the same rules."""

    def test_public_class_async_method_kept(self, tmp_path: Path) -> None:
        """Public class async method keeps underscore."""
        src = (
            "__all__ = ['Public']\n"
            'class Public:\n'
            '    async def _fetch(self):\n'
            '        pass\n'
            'p = Public()\n'
            'p._fetch()\n'
        )
        prev, result = run_hook(tmp_path, src)
        assert result == src
        assert '_fetch' in result


class TestNoqaProtection:
    """noqa directive suppresses stripping for methods."""

    def test_method_with_noqa_kept(self, tmp_path: Path) -> None:
        """# noqa on a strippable method keeps its underscore."""
        src = (
            'class _F:\n'
            '    def _x(self):  # noqa\n'
            '        pass\n'
            'f = _F()\n'
            'f._x()\n'
        )
        prev, result = run_hook(tmp_path, src)
        assert result == src
        assert '_x' in result


class TestEdgeCases:
    """Patterns that never get stripped."""

    def test_dunder_method_preserved(self, tmp_path: Path) -> None:
        """Dunder methods always kept."""
        src = (
            'class _F:\n'
            '    def __init__(self):\n'
            '        pass\n'
            'f = _F()\n'
        )
        prev, result = run_hook(tmp_path, src)
        assert result == src
        assert '__init__' in result


class TestAttributeAccessRegression:
    """Regression test: Attribute.attr tracking should not break public class detection."""

    def test_public_class_method_via_attr_access_kept(self, tmp_path: Path) -> None:
        """Method accessed via obj.method() in a class listed in __all__ keeps underscore.

        This is a regression test for a bug where the class definition matching
        only checked for 'class {name}: ' (with trailing space) and failed to match
        'class {name}:' (without trailing space), causing public class methods
        to be incorrectly stripped when the class was in __all__.
        """
        src = """__all__ = ['PublicClass']

class PublicClass:
    def _helper(self):
        pass

obj = PublicClass()
print(obj._helper)
"""
        prev, result = run_hook(tmp_path, src)
        assert '_helper' in result  # Must keep underscore for public class

    def test_public_class_no_trailing_space_kept(self, tmp_path: Path) -> None:
        """Class definition without trailing space after colon is matched."""
        src = """__all__ = ['MyClass']

class MyClass:
    def _internal(self):
        return 42

c = MyClass()
assert c._internal() == 42
"""
        prev, result = run_hook(tmp_path, src)
        assert '_internal' in result  # Must keep underscore
