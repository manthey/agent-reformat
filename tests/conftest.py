from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class ReformatResult:
    """Outcome of running the agent-reformat hook on a source string.

    Attributes:
        before: The source text as written to the temporary file.
        after: The source text read back after the run.
        stdout: Everything the hook wrote to stdout.
        rc: The process-style exit code (SystemExit code, or 0).
        path: The temporary file the source was written to.

    """

    before: str
    after: str
    stdout: str
    rc: int
    path: Path


class Reformat:
    """Driver for invoking the agent-reformat hook against a temp directory.

    The hook is a CLI entry point: it prints violations to stdout and calls
    ``sys.exit``.  Tests only express the input source, the rule selection, and
    the assertions; this class centralises the temp-file write, the argv
    construction, the stdout capture, and the read-back.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    def run(
        self,
        source: str,
        rules: str | Iterable[str] | None = None,
        fix: bool = False,
        filename: str = 'test.py',
        path: Path | None = None,
    ) -> ReformatResult:
        """Run the hook on ``source`` and return a :class:`ReformatResult`.

        Args:
            source: Python source to write to the temporary file.
            rules: Rule selection passed to ``--rules``.  A string is used
                verbatim; an iterable of codes is joined with commas.
            fix: When true, pass ``--fix`` so the file may be rewritten.
            filename: Base name of the temp file, used when ``path`` is None.
            path: Explicit file path, e.g. for private-module tests that need
                an ancestor directory whose name starts with an underscore.

        """
        from hooks.agent_reformat import run as run_hook

        target = path if path is not None else self._tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)

        args = [str(target)]
        if fix:
            args.append('--fix')
        if rules is not None:
            rules_arg = rules if isinstance(rules, str) else ','.join(rules)
            args.extend(['--rules', rules_arg])
        original_stdout = sys.stdout
        captured = io.StringIO()
        rc = 0
        try:
            sys.stdout = captured
            try:
                run_hook(args)
            except SystemExit as exc:
                rc = exc.code if exc.code is not None else 0
        finally:
            sys.stdout = original_stdout
        return ReformatResult(
            before=source,
            after=target.read_text(),
            stdout=captured.getvalue(),
            rc=rc,
            path=target,
        )

    def fix(
        self,
        source: str,
        rules: str | Iterable[str] | None = None,
        filename: str = 'test.py',
        path: Path | None = None,
    ) -> ReformatResult:
        """Shortcut for :meth:`run` with ``fix=True``."""
        return self.run(
            source, rules=rules, fix=True, filename=filename, path=path,
        )

    def check(
        self,
        source: str,
        rules: str | Iterable[str] | None = None,
        filename: str = 'test.py',
        path: Path | None = None,
    ) -> ReformatResult:
        """Shortcut for :meth:`run` with ``fix=False`` (check mode)."""
        return self.run(
            source, rules=rules, fix=False, filename=filename, path=path,
        )


@pytest.fixture
def reformat(tmp_path: Path) -> Reformat:
    """Provide a :class:`Reformat` driver bound to this test's tmp_path."""
    return Reformat(tmp_path)


@pytest.fixture
def tmp_py_file(tmp_path: Path) -> Path:
    """Create a temporary .py file and return its path."""
    return tmp_path / 'test_input.py'
