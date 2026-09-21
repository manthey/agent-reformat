"""Tests for AR04x: leading-underscore modules are fully internal.

If a module lives at a path whose leaf stem, or any ancestor package
directory, starts with a single underscore (e.g. ``foo/_bar/_baz.py``), then
nothing in that module is exported.  All single-leading-underscore identifiers
should therefore be stripped, even without an ``__all__`` and even when the
file itself defines ``__all__``.
"""
from __future__ import annotations

from pathlib import Path


def test_leaf_module_underscore_stripped(tmp_path: Path, reformat) -> None:
    """Module named _baz.py: everything is internal and stripped."""
    src = '_x = 1\nprint(_x)\n\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / 'foo' / '_bar' / '_baz.py')
    out, result = res.stdout, res.after
    assert result == 'x = 1\nprint(x)\n\n'
    assert 'AR041' in out


def test_ancestor_package_underscore_stripped(tmp_path: Path, reformat) -> None:
    """Public leaf under a private package _bar/ is still internal."""
    src = 'def _f():\n    pass\n_f()\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / 'foo' / '_bar' / 'baz.py')
    out, result = res.stdout, res.after
    assert result == 'def f():\n    pass\nf()\n'
    assert 'AR042' in out


def test_public_module_untouched(tmp_path: Path, reformat) -> None:
    """No private component anywhere: existing behavior is preserved."""
    src = '_x = 1\nprint(_x)\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / 'foo' / 'bar' / 'baz.py')
    out, result = res.stdout, res.after
    assert result == src
    assert 'AR041' not in out


def test_all_ignored_in_private_module(tmp_path: Path, reformat) -> None:
    """A private module's __all__ does not shield names from stripping."""
    src = "__all__ = ['_x']\n_x = 1\nprint(_x)\n"
    res = reformat.fix(src, 'AR04', path=tmp_path / '_pkg' / 'mod.py')
    out, result = res.stdout, res.after
    assert result == "__all__ = ['x']\nx = 1\nprint(x)\n"
    assert 'AR041' in out


def test_methods_stripped_in_private_module(tmp_path: Path, reformat) -> None:
    """AR043 strips methods of a private class in a private module."""
    src = (
        'class _K:\n'
        '    def _method(self):\n'
        '        return 1\n'
        'k = _K()\n'
        'print(k._method())\n'
    )
    res = reformat.fix(src, 'AR04', path=tmp_path / '_pkg' / 'mod.py')
    out, result = res.stdout, res.after
    assert 'def method(self):' in result
    assert 'k.method()' in result
    assert 'AR043' in out


def test_nested_functions_stripped_in_private_module(tmp_path: Path, reformat) -> None:
    """AR044 strips nested functions in a private module."""
    src = (
        'def outer():\n'
        '    def _inner():\n'
        '        return 2\n'
        '    return _inner()\n'
    )
    res = reformat.fix(src, 'AR04', path=tmp_path / '_pkg' / 'mod.py')
    out, result = res.stdout, res.after
    assert 'def inner():' in result
    assert 'return inner()' in result
    assert 'AR044' in out


def test_dunder_and_trailing_underscore_preserved(tmp_path: Path, reformat) -> None:
    """Private-module detection must not strip dunder or trailing-underscore."""
    src = '__version__ = 1\nprint(__version__)\ncls_ = 2\nprint(cls_)\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / '_pkg' / 'mod.py')
    result = res.after
    assert result == src
    assert '__version__' in result
    assert 'cls_' in result


def test_dunder_directory_not_private(tmp_path: Path, reformat) -> None:
    """A directory named __pycache__ is not a private-module marker."""
    src = '_x = 1\nprint(_x)\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / 'pkg' / '__pycache__' / 'mod.py')
    result = res.after
    assert result == src


def test_trailing_underscore_directory_not_private(tmp_path: Path, reformat) -> None:
    """A directory named foo_ is not a private-module marker."""
    src = '_x = 1\nprint(_x)\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / 'foo_' / 'mod.py')
    result = res.after
    assert result == src


def test_noqa_still_protects_in_private_module(tmp_path: Path, reformat) -> None:
    """Explicit noqa overrides private-module stripping."""
    src = '_x = 1  # noqa\nprint(_x)\n'
    res = reformat.fix(src, 'AR04', path=tmp_path / '_pkg' / 'mod.py')
    result = res.after
    assert '_x' in result
