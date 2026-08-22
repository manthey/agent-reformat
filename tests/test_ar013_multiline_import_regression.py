"""Regression test for AR013 bug: blank lines after multi-line imports were being removed."""
from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

from hooks.agent_reformat import run as run_hook


def run_fix(tmp_path: Path, source_code: str) -> str:
    """Run agent-reformat in fix mode on a temp file. Returns modified content."""
    f = tmp_path / 'test.py'
    f.write_text(source_code)
    original_stdout = sys.stdout
    captured = StringIO()
    try:
        sys.stdout = captured
        try:
            run_hook([str(f), '--fix', '--rules', 'AR013'])
        except SystemExit:
            pass
    finally:
        sys.stdout = original_stdout
    return f.read_text()


class TestAR013MultilineImportRegression:
    """Test that AR013 preserves blank lines after multi-line import statements.

    Regression test for the bug where AR013 incorrectly removed blank lines
    immediately after multi-line import statements when the import spanned
    multiple lines.
    """

    def test_multiline_from_import_trailing_blank_preserved(self, tmp_path: Path) -> None:
        """Blank line after a multi-line 'from ... import' should be preserved."""
        src = """from .test_annotations import (makeLargeSampleAnnotation, sampleAnnotation,
                               sampleAnnotationEmpty,
                               sampleAnnotationWithMetadata,
                               sampleAnnotationWithPointsAndMetadata)

pytestmark = 1
"""
        after = run_fix(tmp_path, src)
        # The blank line between the from-import and pytestmark should be
        # preserved
        assert 'sampleAnnotationWithPointsAndMetadata)\n\npytestmark' in after

    def test_multiline_from_import_no_blank_following(self, tmp_path: Path) -> None:
        """When no blank follows multi-line import, behavior is correct."""
        src = """from .test_annotations import (makeLargeSampleAnnotation, sampleAnnotation,
                               sampleAnnotationEmpty)
pytestmark = 1
"""
        after = run_fix(tmp_path, src)
        # Should not add a blank that wasn't there
        assert 'sampleAnnotationEmpty)\npytestmark' in after

    def test_multiline_import_inside_function(self, tmp_path: Path) -> None:
        """Multi-line import inside a function should preserve trailing blank."""
        src = """def foo():
    from os import (path,
                    getcwd)

    return path


x = 1
"""
        after = run_fix(tmp_path, src)
        # The blank line after the multi-line import should be preserved
        assert 'getcwd)\n\n    return' in after

    def test_original_bug_case(self, tmp_path: Path) -> None:
        """Replicate the original bug case from the issue."""
        src = """import copy
import json
import os
import struct

import pytest

from . import girder_utilities as utilities
from .test_annotations import (makeLargeSampleAnnotation, sampleAnnotation,
                               sampleAnnotationEmpty,
                               sampleAnnotationWithMetadata,
                               sampleAnnotationWithPointsAndMetadata)

pytestmark = pytest.mark.girder
"""
        after = run_fix(tmp_path, src)
        # Find the multi-line import and verify blank line is preserved after
        lines = after.split('\n')
        found_multiline_import_end = False
        for i, line in enumerate(lines):
            if 'sampleAnnotationWithPointsAndMetadata)' in line:
                # Check that next line (i+1) is blank
                if i + 1 < len(lines):
                    assert lines[i + 1].strip() == '', (
                        f'Expected blank line after multi-line import at line {i+2}, '
                        f'but got: "{lines[i + 1]}"'
                    )
                    found_multiline_import_end = True
                    break
        assert found_multiline_import_end, 'Could not find multi-line import end'
