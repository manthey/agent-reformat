"""Tests for AR005 / AR045: leading-underscore class names.

AR005 unconditionally strips a single leading underscore from top-level class
names (application-code behavior).  AR045 only strips class names that are not
exported (library behavior): a class is non-exported when its name starts with
an underscore, when ``__all__`` is defined and omits it, or when the module
itself is internal.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path


def run_fix(path: Path, src: str, rules: str) -> tuple[str, str]:
    """Run agent-reformat --fix on *path*. Returns (stdout, after)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src)
    from hooks.agent_reformat import run
    out = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = out
        try:
            run([str(path), f'--rules={rules}', '--fix'])
        except SystemExit:
            pass
    finally:
        sys.stdout = orig
    return out.getvalue(), path.read_text()


class TestAR005Unconditional:
    """AR005 strips class names regardless of export status."""

    def test_class_stripped_without_all(self, tmp_path: Path) -> None:
        src = 'class _Klass:\n    pass\nk = _Klass()\nprint(k)\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert 'class Klass:' in result
        assert 'k = Klass()' in result
        assert 'AR005' in out

    def test_class_kept_when_no_underscore(self, tmp_path: Path) -> None:
        src = 'class Klass:\n    pass\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert result == src
        assert 'AR005' not in out

    def test_dunder_class_preserved(self, tmp_path: Path) -> None:
        src = 'class __Meta__:\n    pass\nprint(__Meta__)\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert '__Meta__' in result

    def test_trailing_underscore_class_preserved(self, tmp_path: Path) -> None:
        src = 'class class_:\n    pass\nprint(class_)\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert 'class class_:' in result

    def test_class_in_all_still_stripped_by_ar005(self, tmp_path: Path) -> None:
        src = "__all__ = ['_Klass']\nclass _Klass:\n    pass\nprint(_Klass)\n"
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert 'class Klass:' in result

    def test_noqa_protects_class(self, tmp_path: Path) -> None:
        src = 'class _Klass:  # noqa\n    pass\nprint(_Klass)\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert '_Klass' in result

    def test_unused_class_kept(self, tmp_path: Path) -> None:
        """Unused classes are left alone, matching AR001-AR004 behavior."""
        src = 'class _Unused:\n    pass\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert result == src
        assert 'AR005' not in out

    def test_class_used_via_attribute_kept_stripped(self, tmp_path: Path) -> None:
        """Attribute-based usage still marks the class as used."""
        src = (
            'class _Holder:\n'
            '    pass\n'
            '_h = _Holder()\n'
            'print(_h)\n'
        )
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert 'class Holder:' in result
        assert 'AR005' in out


class TestAR045NonExported:
    """AR045 only strips classes that are not exported."""

    def test_underscore_class_kept_without_all(self, tmp_path: Path) -> None:
        """Without __all__, every class is implicitly public, so kept."""
        src = 'class _Klass:\n    pass\nk = _Klass()\nprint(k)\n'
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert result == src
        assert 'AR045' not in out

    def test_class_in_all_kept(self, tmp_path: Path) -> None:
        src = "__all__ = ['_Klass']\nclass _Klass:\n    pass\nprint(_Klass)\n"
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert 'class _Klass:' in result
        assert 'AR045' not in out

    def test_class_not_in_all_stripped(self, tmp_path: Path) -> None:
        src = ("__all__ = ['Other']\nclass _Klass:\n    pass\n"
               'print(_Klass)\n')
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert 'class Klass:' in result
        assert 'AR045' in out

    def test_class_without_underscore_untouched(self, tmp_path: Path) -> None:
        src = '__all__ = ["Other"]\nclass Klass:\n    pass\nprint(Klass)\n'
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert 'class Klass:' in result
        assert 'AR045' not in out

    def test_noqa_protects_class(self, tmp_path: Path) -> None:
        src = "__all__ = ['Other']\nclass _Klass:  # noqa\n    pass\nprint(_Klass)\n"
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert '_Klass' in result

    def test_dunder_class_preserved(self, tmp_path: Path) -> None:
        src = "__all__ = ['Other']\nclass __P:\n    pass\nprint(__P)\n"
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert '__P' in result

    def test_unused_class_kept(self, tmp_path: Path) -> None:
        """Unused classes are left alone, matching other underscore rules."""
        src = "__all__ = ['Other']\nclass _Unused:\n    pass\n"
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert result == src
        assert 'AR045' not in out


class TestAR045PrivateModule:
    """In a private module every class is internal."""

    def test_class_stripped_in_private_module(self, tmp_path: Path) -> None:
        src = 'class _Klass:\n    pass\nk = _Klass()\nprint(k)\n'
        out, result = run_fix(tmp_path / '_pkg' / 'mod.py', src, 'AR045')
        assert 'class Klass:' in result
        assert 'k = Klass()' in result
        assert 'AR045' in out

    def test_class_in_all_still_stripped_in_private_module(
        self, tmp_path: Path,
    ) -> None:
        src = "__all__ = ['_Klass']\nclass _Klass:\n    pass\nprint(_Klass)\n"
        out, result = run_fix(tmp_path / '_pkg' / 'mod.py', src, 'AR045')
        assert 'class Klass:' in result


class TestRuleSelectivity:
    """A single active rule must not strip other kinds."""

    def test_ar005_does_not_strip_functions_or_vars(
        self, tmp_path: Path,
    ) -> None:
        src = (
            '_x = 1\n'
            'def _f():\n'
            '    pass\n'
            '_f()\n'
            'print(_x)\n'
        )
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert '_x' in result
        assert '_f' in result
        assert 'AR005' not in out

    def test_ar045_does_not_strip_methods_or_functions(
        self, tmp_path: Path,
    ) -> None:
        src = (
            "__all__ = ['Other']\n"
            'def _f():\n'
            '    pass\n'
            '_f()\n'
            'class _K:\n'
            '    def _m(self):\n'
            '        pass\n'
            'k = _K()\n'
            'k._m()\n'
        )
        out, result = run_fix(tmp_path / 'lib.py', src, 'AR045')
        assert 'class K:' in result
        assert 'def _m(self):' in result
        assert 'def _f():' in result

    def test_ar001_does_not_strip_classes(self, tmp_path: Path) -> None:
        src = 'class _K:\n    pass\n_x = _K()\nprint(_x)\n'
        out, result = run_fix(tmp_path / 'app.py', src, 'AR001')
        assert 'class _K:' in result
        assert 'class K:' not in result
        assert 'x = _K()' in result


class TestAR005WithMethods:
    """Stripping a class name and its methods in one pass."""

    def test_class_and_method_stripped_together(self, tmp_path: Path) -> None:
        src = (
            'class _Klass:\n'
            '    def _method(self):\n'
            '        return 1\n'
            'k = _Klass()\n'
            'print(k._method())\n'
        )
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005,AR003')
        assert 'class Klass:' in result
        assert 'def method(self):' in result
        assert 'k = Klass()' in result
        assert 'k.method()' in result

    def test_class_referenced_in_module_scope(self, tmp_path: Path) -> None:
        src = (
            'class _A:\n'
            '    pass\n'
            'class _B(_A):\n'
            '    pass\n'
            'print(_B)\n'
        )
        out, result = run_fix(tmp_path / 'app.py', src, 'AR005')
        assert 'class A:' in result
        assert 'class B(A):' in result
        assert 'print(B)' in result
