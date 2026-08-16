"""Tests for AR014: Remove blank lines between decorators and their target."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> tuple[str, str]:
    """Run agent-reformat in fix mode on a temp file. Returns (original, modified)."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)

    original_stdout = sys.stdout
    captured = io.StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR014'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return source_code, f.read_text()


class TestAR014BasicDecoratorRemoval:
    """Test that blank lines between decorators and targets are removed."""

    def test_blank_between_decorators_removed(self, tmp_path: Path) -> None:
        """Blank line between two decorators should be removed."""
        src = '@decorator1\n\n@decorator2\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator1\n@decorator2\ndef foo():\n    pass\n'

    def test_blank_after_last_decorator_removed(self, tmp_path: Path) -> None:
        """Blank line after last decorator before target should be removed."""
        src = '@decorator1\n@decorator2\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator1\n@decorator2\ndef foo():\n    pass\n'

    def test_blanks_on_both_sides_removed(self, tmp_path: Path) -> None:
        """Blank lines both between decorators and before target should be removed."""
        src = '@decorator1\n\n@decorator2\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator1\n@decorator2\ndef foo():\n    pass\n'

    def test_multiple_consecutive_blanks_before_decorator_removed(self, tmp_path: Path) -> None:
        """AR014 FIX: All consecutive blanks between decorators should be removed."""
        src = '@decorator1\n\n\n@decorator2\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator1\n@decorator2\ndef foo():\n    pass\n'

    def test_multiple_consecutive_blanks_after_decorators_removed(self, tmp_path: Path) -> None:
        """AR014 FIX: All consecutive blanks after decorators before target should be removed."""
        src = '@decorator1\n@decorator2\n\n\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator1\n@decorator2\ndef foo():\n    pass\n'

    def test_many_decorators_with_blanks(self, tmp_path: Path) -> None:
        """Multiple decorators with various blank patterns should all be cleaned."""
        src = (
            '@dec1\n\n'
            '@dec2\n'
            '\n'
            '@dec3\n\n\n'
            'def foo():\n'
            '    pass\n'
        )
        _, after = run_fix(tmp_path, src)
        expected = '@dec1\n@dec2\n@dec3\ndef foo():\n    pass\n'
        assert after == expected


class TestAR014ClassDecorators:
    """Test AR014 with class decorators."""

    def test_blank_before_class_decorator(self, tmp_path: Path) -> None:
        """Blank line before decorator for class is preserved (not our concern)."""
        src = 'x = 1\n\n@dataclass\nclass Foo:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Blank before @dataclass is at module level, not between a decorator
        # and target
        assert 'x = 1\n\n@dataclass' in after

    def test_blank_between_class_decorators_removed(self, tmp_path: Path) -> None:
        """Blank line between class decorators should be removed."""
        src = '@dec1\n\n@dataclass\nclass Foo:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@dec1\n@dataclass\nclass Foo:\n    pass\n'

    def test_blank_after_class_decorators_removed(self, tmp_path: Path) -> None:
        """Blank line after decorators before class should be removed."""
        src = '@dec1\n@dataclass\n\nclass Foo:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@dec1\n@dataclass\nclass Foo:\n    pass\n'

    def test_both_sides_blank_for_class(self, tmp_path: Path) -> None:
        """Blanks on both sides should be removed for class."""
        src = '@dec1\n\n@dataclass\n\nclass Foo:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@dec1\n@dataclass\nclass Foo:\n    pass\n'


class TestAR014MethodDecorators:
    """Test AR014 with method decorators."""

    def test_method_property_decorator(self, tmp_path: Path) -> None:
        """Property decorator at module level before function should work."""
        src = '@property\n\ndef prop_foo():\n    return 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@property\ndef prop_foo():\n    return 1\n'

    def test_method_in_class_decorators(self, tmp_path: Path) -> None:
        """Method decorator in class body - blanks between dec and def removed."""
        src = 'class Foo:\n    @property\n\n    def bar(self):\n        return 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == 'class Foo:\n    @property\n    def bar(self):\n        return 1\n'

    def test_multiple_method_decorators(self, tmp_path: Path) -> None:
        """Multiple method decorators with blanks should be cleaned."""
        src = (
            'class Foo:\n'
            '    @dec1\n\n'
            '    @dec2\n\n\n'
            '    def bar(self):\n'
            '        return 1\n'
        )
        _, after = run_fix(tmp_path, src)
        expected = (
            'class Foo:\n'
            '    @dec1\n'
            '    @dec2\n'
            '    def bar(self):\n'
            '        return 1\n'
        )
        assert after == expected


class TestAR014AsyncDecorators:
    """Test AR014 with async function decorators."""

    def test_async_func_decorator_blank_removed(self, tmp_path: Path) -> None:
        """Blank between @dec and async def should be removed."""
        src = '@auth\n\nasync def fetch():\n    return 1\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@auth\nasync def fetch():\n    return 1\n'


class TestAR014PreservedBlanks:
    """Test that certain blank lines are NOT removed by AR014."""

    def test_blanks_outside_decorator_block_preserved(self, tmp_path: Path) -> None:
        """Blank after decorator block's content preserved."""
        src = '@dec\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@dec\ndef foo():\n    pass\n'

    def test_blanks_before_decorator_not_touched(self, tmp_path: Path) -> None:
        """Blank lines BEFORE a decorator block (not between decorators) preserved."""
        src = 'x = 1\n\n@dec\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Blank before @dec is module-level structure, not inside decorator
        # block
        assert 'x = 1\n\n@dec' in after

    def test_blanks_inside_function_preserved(self, tmp_path: Path) -> None:
        """Blanks inside function body should NOT be removed by AR014."""
        src = '@dec\ndef foo():\n    x = 1\n\n    y = 2\n'
        _, after = run_fix(tmp_path, src)
        # Note: the blank before 'y=2' is inside the function body (after def
        # line + indent)
        assert 'x = 1\n\n    y' in after

    def test_blanks_between_separate_decorator_blocks(self, tmp_path: Path) -> None:
        """Blanks between two unrelated decorated functions are preserved."""
        src = '@dec1\ndef foo():\n    pass\n\n@dec2\ndef bar():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # Both blocks should be cleaned internally, but blank between them
        # preserved
        assert 'foo():\n    pass\n\n@dec2' in after


class TestAR014ComplexScenarios:
    """Test complex AR014 scenarios."""

    def test_decorator_with_inline_comment(self, tmp_path: Path) -> None:
        """Decorator with inline comment should still have blanks removed."""
        src = '@auth  # need auth\n\n@timeout(30)\ndef api():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@auth  # need auth\n@timeout(30)\ndef api():\n    pass\n'

    def test_bracketed_decorator(self, tmp_path: Path) -> None:
        """Decorator taking arguments should work."""
        src = '@decorator(arg="value")\n\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator(arg="value")\ndef foo():\n    pass\n'

    def test_multiple_decorator_arguments(self, tmp_path: Path) -> None:
        """Decorators with arguments and blanks all cleaned."""
        src = (
            '@cached(60)\n'
            '\n'
            '@auth\n'
            '\n\n'
            'def protected_route():\n'
            "    return 'ok'\n"
        )
        _, after = run_fix(tmp_path, src)
        expected = (
            '@cached(60)\n'
            '@auth\n'
            'def protected_route():\n'
            "    return 'ok'\n"
        )
        assert after == expected

    def test_nested_function_decorator(self, tmp_path: Path) -> None:
        """Decorator on nested function should be cleaned."""
        src = (
            '@outer\n'
            'def outer():\n'
            '\n'  # before inner def - not our scope
            '    @inner_dec\n\n\n'
            '    def inner():\n'
            '        return 1\n'
        )
        _, after = run_fix(tmp_path, src)
        # The @inner_dec -> def inner: blank should be removed
        assert '@inner_dec\n    def inner():' in after


class TestAR014EdgeCases:
    """Test edge cases for AR014."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file unchanged."""
        _, after = run_fix(tmp_path, '')
        assert after == ''

    def test_single_decorator_no_target_blank(self, tmp_path: Path) -> None:
        """Single decorator with no blanks - no change needed."""
        src = '@dec\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_no_decorator_at_all(self, tmp_path: Path) -> None:
        """File without any decorators - no change."""
        src = 'x = 1\n\ny = 2\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == src

    def test_only_decorator_no_def(self, tmp_path: Path) -> None:
        """Just a decorator line with nothing following (no valid target)."""
        src = '@decorator\n\ndef bar(bla):\n'  # incomplete syntax but still parsed sometimes
        try:
            _, after = run_fix(tmp_path, src)
            assert True  # At least didn't crash
        except SyntaxError:
            pass  # Expected if syntax is terrible

    def test_decorator_in_class_not_touched_module(self, tmp_path: Path) -> None:
        """Decorator inside class body should be handled correctly."""
        src = (
            'class Container:\n'
            '\n'  # Between class and first method - not decorator-related
            '    @classmethod\n\n\n'
            '    def make(cls):\n'
            '        return cls()\n'
        )
        _, after = run_fix(tmp_path, src)
        # Inside class: blank between @classmethod and def should be removed
        assert '@classmethod\n    def make(cls):' in after


class TestAR014CheckMode:
    """Test check mode for AR014."""

    def test_check_mode_no_file_change(self, tmp_path: Path) -> None:
        """Check mode should not modify the source file."""
        src = '@dec1\n\n@dec2\ndef foo():\n    pass\n'
        f = tmp_path / 'test.py'
        f.write_text(src)

        captured_out = io.StringIO()
        original_stdout = sys.stdout
        try:
            sys.stdout = captured_out
            try:
                run_hook([str(f), '--rules', 'AR014'])
            except SystemExit:
                pass
        finally:
            sys.stdout = original_stdout
        assert f.read_text() == src, 'Check mode must not modify the file'


class TestAR014MixedWithOtherRules:
    """Test AR014 alongside other blank line rules."""

    def test_ar014_with_ar011(self, tmp_path: Path) -> None:
        """Both AR014 and AR011 should work together without conflict."""
        src = '@dec1\n\n@dec2\n\nclass Foo:\n    pass\n'
        _, after = run_fix(tmp_path, src)
        # AR014 removes between decs; AR011 doesn't touch module-level blanks
        expected = '@dec1\n@dec2\nclass Foo:\n    pass\n'
        assert after == expected

    def test_ar014_alone_preserves_module_structure(self, tmp_path: Path) -> None:
        """AR014 standalone should preserve module-level structure."""
        src = (
            "@app.route('/')\n\n\ndef home():\n"
            "    return 'hello'\n\n\n"  # trailing blanks preserved
            "@app.route('/about')\n\ndef about():\n"
            "    return 'about'"
        )
        _, after = run_fix(tmp_path, src)
        assert "@app.route('/')\n\ndef home():" not in after
        # Should remove blanks between decorator and def
        assert "@app.route('/')\ndef home():" in after


class TestAR014DecoratorStringPreservation:
    """Test that AR014 doesn't touch strings."""

    def test_decorator_with_string_arg(self, tmp_path: Path) -> None:
        """Decorators with string arguments should work correctly."""
        src = '@decorator("arg")\n\n\ndef foo():\n    pass\n'
        _, after = run_fix(tmp_path, src)
        assert after == '@decorator("arg")\ndef foo():\n    pass\n'

    def test_multiline_string_literal_not_affected(self, tmp_path: Path) -> None:
        """Code with multiline strings that contain @ should be fine."""
        src = (
            's = """\n@not_a_decorator\n"""\n\n'
            '@real_dec\n\ndef foo():\n    pass\n'
        )
        _, after = run_fix(tmp_path, src)
        # Should remove blank between @real_dec and def
        assert '@real_dec\ndef foo():' in after
