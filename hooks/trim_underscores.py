#!/usr/bin/env python3
# /// script
# name = "trim_underscores"
# requires-python = ">=3.9"
# dependencies = []
# ///

import argparse
import ast
import re
import sys
from pathlib import Path


def parse_source(source):
    """Parse source code into an AST tree safely."""
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def get_usage_counts(tree):
    """Count occurrences of identifiers used in the file."""
    usages = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            usages[node.id] = usages.get(node.id, 0) + 1
    return usages


def get_definitions(tree):
    """Extract all defined identifiers (functions, classes, variables)."""
    definitions = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions.add(target.id)
    return definitions


def get_clean_name(ident, usages):
    """Determine the cleaned identifier name based on strict rules."""
    # 1. Must start with single leading underscore but not a dunder
    if not ident.startswith('_') or ident.startswith('__'):
        return None
    # 2. EXCEPT functions/methods/variables with trailing underscores
    if ident.endswith('_'):
        return False
    # 3. Must be actively used! Unused vars are often intentional placeholders
    usages_count = usages.get(ident, 0)
    if usages_count == 0:
        return None
    # Return the cleaned name (all leading underscores stripped)
    return ident.lstrip('_')


def strip_underscores(filepath):
    """Strip leading underscores from defined and used identifiers robustly."""
    file_path = Path(filepath)
    source = file_path.read_text(encoding='utf-8')

    tree = parse_source(source)
    if not tree:
        return False
    # Get definitions and active usage counts
    raw_usages = get_usage_counts(tree)
    raw_definitions = get_definitions(tree)

    replacements = {}
    for ident in raw_definitions:
        new_name = get_clean_name(ident, raw_usages)

        # Explicit type check prevents boolean truthiness bugs from leaking!
        if isinstance(new_name, str):
            replacements[ident] = new_name
    if not replacements:
        return False
    new_source = source

    # Replace by sorted length descending to avoid accidental substring
    # replacement issues (e.g., '_a' vs '_abc')
    for old_name, new_name in sorted(replacements.items(), key=len, reverse=True):
        pattern = r'\b' + re.escape(old_name) + r'\b'
        new_source = re.sub(pattern, new_name, new_source)
    file_path.write_text(new_source, encoding='utf-8')
    return True


def should_keep_blank_line(
    prev_text, prev_indent, curr_text, curr_indent,
    indent_cause, code_lines_since_last_blank,
    min_gap, has_multiple_blanks=False,
):
    """Determine if a pending blank line should be retained based on rules."""
    prev_starts_import = prev_text.startswith(('import ', 'from '))
    curr_starts_import = curr_text.startswith(('import ', 'from '))
    # Rule 1: Allow multiple consecutive blank lines before any def/class/decorator
    # (for PEP8 E302 compliance). When we have 2+ blanks preceding a top-level
    # definition, keep at most two of them rather than stripping all.
    if has_multiple_blanks:
        return any(
            curr_text.startswith(pfx)
            for pfx in ('def ', 'async def ', 'class ', '@')
        )
    # Rule 2: Keep for import blocks (start/end/middle).
    keep_for_imports = \
        (prev_starts_import and not curr_starts_import) or \
        (prev_starts_import and curr_starts_import)
    # Rule 3: Keep before a function/class/decorator definition.
    def_or_class_def = any(curr_text.startswith(pfx) for pfx in (
        'def ', 'async def ', 'class ', '@'))
    if keep_for_imports or def_or_class_def:
        return True
    # Rule 4: Outdenting from a function/class block.
    if prev_indent > curr_indent:
        for indent_level in range(curr_indent + 4, prev_indent + 4, 4):
            if indent_cause.get(indent_level) in ('def', 'class'):
                return True
    # Rule 5: Long logical section inside same-indent code.
    gap_reached = code_lines_since_last_blank >= min_gap
    same_indent = prev_indent == curr_indent
    return same_indent and gap_reached


def fix_blanks(filepath, min_gap=3):
    """Remove excessive blank lines between code blocks.

    For PEP8 E302 compliance (two blank lines before top-level
    function/class definitions), consecutive blanks at module level
    preceding a def/class are handled specially: up to two are kept,
    any more are stripped.
    """
    source = Path(filepath).read_text(encoding='utf-8')
    lines = source.splitlines(keepends=True)
    output_lines = []
    pending_blank = False
    code_lines_since_last_blank = 0
    consecutive_blanks = 0
    prev_indent = 0
    prev_text = ''
    # Track what started the current indent block (e.g., 'def', 'class', etc.)
    # Standard blocks are typically multiples of 4.
    indent_cause = {0: 'other'}
    for line in lines:
        curr_text = line.strip()
        curr_indent = len(line) - len(line.lstrip())
        if not curr_text:  # It's a blank or whitespace-only line.
            pending_blank = True
            consecutive_blanks += 1
            continue
        # Detect outdenting back to module level (indent 0) after nested blocks.
        outdented_to_top = curr_indent == 0 and prev_indent > 0
        # If we just had blank lines, decide whether to keep any (and how many).
        if pending_blank:
            has_multiple = consecutive_blanks >= 2
            should_keep = should_keep_blank_line(
                prev_text, prev_indent, curr_text, curr_indent,
                indent_cause, code_lines_since_last_blank, min_gap,
                has_multiple_blanks=has_multiple,
            )
            if has_multiple and curr_indent == 0 and any(
                curr_text.startswith(pfx)
                for pfx in ('def ', 'async def ', 'class ', '@')
            ):
                # PEP8 E302: keep up to 2 blanks before top-level defs/classes/decorators
                output_lines.append('\n\n')
            elif outdented_to_top and consecutive_blanks >= 2:
                # PEP8 E305: after nested block, need 2 blanks at module level too
                output_lines.append('\n\n')
            elif should_keep:
                output_lines.append('\n')
                code_lines_since_last_blank = 0
            consecutive_blanks = 0
            pending_blank = False
        # Update indent cause for the next block.
        if curr_indent > prev_indent:
            is_prev_def = prev_text.startswith(('def ', 'async def '))
            if is_prev_def:
                indent_cause[curr_indent] = 'def'
            elif prev_text.startswith('class '):
                indent_cause[curr_indent] = 'class'
            else:
                indent_cause[curr_indent] = 'other'
        output_lines.append(line)
        code_lines_since_last_blank += 1
        prev_indent = curr_indent
        prev_text = curr_text
    # Ensure proper spacing at end of file (E305: 2 blank lines after last def/class).
    if pending_blank:
        if any(
            prev_text.strip().endswith(suffix)
            for suffix in ('def ', 'async def ', 'class ')
        ) or consecutive_blanks >= 2:
            output_lines.append('\n\n')
        else:
            output_lines.append('\n')
    new_source = ''.join(output_lines)
    if new_source != source:
        Path(filepath).write_text(new_source, encoding='utf-8')
        return True
    return False


def run():
    """Entry point for pre-commit and standalone CLI usage."""
    parser = argparse.ArgumentParser(
        description='Trim intentional leading underscores and excessive blank lines '
                    'from Python scripts generated by LLMs.',
    )
    parser.add_argument('files', nargs='+', help='List of .py files to process.')
    parser.add_argument(
        '--remove-underscores', '--underscores',
        action='store_true', default=False,
        help=(
            'Remove single leading underscores from identifiers. Rationale: '
            'LLMs often pretend scripts are libraries by prefixing everything '
            'with underscores to appease linters. This aggressively strips them '
            'unless they are dunders (__*) or the exact single underscore (_) '
            'for explicitly unused vars. If a variable is assigned but truly used '
            'elsewhere, stripping this prefix intentionally triggers linter '
            'warnings, prompting us to use it or delete the code block.'
        ),
    )
    parser.add_argument(
        '--remove-blank-lines', '--blanks',
        action='store_true', default=False,
        help=(
            'Remove excessive blank lines between code blocks. Default skips '
            'structural ones and allows one every %(default)s+ lines if '
            'applicable. Rationale: PEP8 recommends sparing blank lines for '
            'conceptual blocks, but LLMs overuse them. This keeps necessary '
            'structural spacing (imports, defs/classes outdent/in-dent) while '
            'clutters fewer logical sections. Note that your local flake8/ruff '
            'rules should not enforce extra spacing (e.g., pycodestyle E302) '
            'before using in CI.'
        ),
    )
    parser.add_argument(
        '--blank-lines-gap', type=int, default=3,
        help=(
            'Minimum number of consecutive code lines required before a new '
            'blank line is permitted elsewhere. Default is %(default)s.'
        ),
    )
    args = parser.parse_args()

    changed = False
    for filepath in args.files:
        if not filepath.endswith('.py'):
            continue
        try:
            # Run underscore stripping (AST based)
            if args.remove_underscores and strip_underscores(filepath):
                print(f'Stripped leading underscores from {filepath}')
                changed = True
            if args.remove_blank_lines:
                gap_val = args.blank_lines_gap
                if fix_blanks(filepath, min_gap=gap_val):
                    print(f'Stripped excessive blank lines from {filepath}')
                    changed = True
        except Exception:
            import traceback
            print(f'Failed to process {filepath}:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    sys.exit(1 if changed else 0)


if __name__ == '__main__':
    run()
