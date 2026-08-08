#!/usr/bin/env python3
# /// script
# name = "trim_underscores"
# requires-python = ">=3.9"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

try:
    from . import rules as _rules_mod  # pip / tests / -m
except ImportError:  # standalone CLI
    parent = str(Path(__file__).resolve().parent.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import hooks.rules as _rules_mod

lookup = _rules_mod.lookup
expand_shorthand = _rules_mod.expand_shorthand
validate_rules = _rules_mod.validate_rules
resolve_rules = _rules_mod.resolve_rules


def collect_definitions_by_type(tree):
    """Return dict of {ident: variable/function/method} scoped to module-level only."""
    defs = {}
    for node in getattr(tree, 'body', []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[node.name] = 'function'
        elif isinstance(node, ast.ClassDef):
            for inner_node in getattr(node, 'body', []):
                if isinstance(inner_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs[inner_node.name] = 'method'
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = getattr(node, 'targets', []) or [getattr(node,
                                                               'target', None)]
            for tgt in targets:
                if tgt and isinstance(tgt, ast.Name):
                    defs[tgt.id] = 'variable'
    return defs


def strip_underscores(filepath, rules, dry_run=False, show=False):
    """Strip underscores per MPH001-003 rules."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    usages = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            usages[node.id] = usages.get(node.id, 0) + 1
    raw_defs = collect_definitions_by_type(tree)
    replacements = {}

    underscore_codes = expand_shorthand('underscores') or (
        'MPH001', 'MPH002', 'MPH003')
    active_underscore_rules = set(rules) & set(underscore_codes)
    if not active_underscore_rules:
        return False
    for ident, kind in raw_defs.items():
        if not ident.startswith('_') or ident.startswith('__'):
            continue
        if ident.endswith('_'):
            continue
        if usages.get(ident, 0) == 0:
            continue
        kept = False
        for r in active_underscore_rules:
            entry = lookup(r)
            g = entry.get('group') or ''
            code = (entry.get('code') or '').upper()
            if g == 'underscores':
                if kind == 'variable' and code == 'MPH001':
                    kept = True
                elif kind == 'function' and code == 'MPH002':
                    kept = True
                elif kind == 'method' and code == 'MPH003':
                    kept = True
        if not kept:
            continue
        replacements[ident] = ident.lstrip('_')
    if not replacements:
        return False
    new_source = source
    for old, new in sorted(replacements.items(), key=len, reverse=True):
        pattern = r'\b' + re.escape(old) + r'\b'
        new_source = re.sub(pattern, new, new_source)
    if show:
        print(new_source.rstrip())
    if not dry_run:
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_source)
    return True


def fix_blanks(filepath, rules, min_gap=3, dry_run=False, show=False):
    """Apply MPH011-015 to clean up blank lines."""
    active_rules = set(rules) if rules else set()

    with open(filepath, encoding='utf-8', newline='') as f:
        source = f.read()
    line_end = '\r\n' if '\r\n' in source else '\n'
    lines = source.splitlines(keepends=True)
    output = []
    pending_blank = False
    code_lines_since_blank = 0
    consecutive_blanks = 0
    prev_indent = 0
    prev_text = ''
    indent_cause = {0: 'other'}
    gap = min_gap

    for line in lines:
        curr_text = line.strip()
        curr_indent = len(line) - len(line.lstrip())

        if not curr_text:
            pending_blank = True
            consecutive_blanks += 1
            continue
        outdented_to_top = curr_indent == 0 and prev_indent > 0

        if pending_blank:
            has_many = consecutive_blanks >= 2
            write_pep8_two = False

            if ('MPH011' in active_rules and has_many and
                    curr_indent == 0):
                starts_def = any(
                    curr_text.startswith(pfx) for pfx in (
                        'def ', 'async def ', 'class ', '@'))
                if starts_def:
                    output.append(line_end + line_end)
                    write_pep8_two = True
            if not write_pep8_two:
                pi = prev_text.startswith(('import ', 'from '))
                ci = curr_text.startswith(('import ', 'from '))
                keep_for_imports = (
                    'MPH013' in active_rules and ((pi and not ci) or
                                                  (pi and ci)))
                keep_for_outdent = False
                if 'MPH014' in active_rules and prev_indent > curr_indent:
                    for lvl in range(curr_indent + 4,
                                     prev_indent + 4, 4):
                        if indent_cause.get(lvl) in ('def', 'class'):
                            keep_for_outdent = True
                gap_reached = code_lines_since_blank >= gap
                same_indent = prev_indent == curr_indent

                should_keep = False
                starts_def = any(
                    curr_text.startswith(pfx) for pfx in (
                        'def ', 'async def ', 'class ', '@'))
                if keep_for_imports or starts_def:
                    should_keep = True
                elif keep_for_outdent:
                    should_keep = True
                elif same_indent and gap_reached:
                    should_keep = True
                if write_pep8_two:
                    pass
                elif outdented_to_top and has_many:
                    output.append(line_end + line_end)
                elif should_keep:
                    output.append(line_end)
                    code_lines_since_blank = 0
            consecutive_blanks = 0
            pending_blank = False
        if curr_indent > prev_indent:
            is_prev_def = prev_text.startswith(('def ', 'async def '))
            if is_prev_def:
                indent_cause[curr_indent] = 'def'
            elif prev_text.startswith('class '):
                indent_cause[curr_indent] = 'class'
            else:
                indent_cause[curr_indent] = 'other'
        output.append(line)
        code_lines_since_blank += 1
        prev_indent = curr_indent
        prev_text = curr_text
    if pending_blank:
        last_def_class = any(prev_text.strip().endswith(sfx) for sfx in (
            'def ', 'async def ', 'class '))
        if last_def_class or has_many:
            output.append(line_end + line_end)
        elif active_rules & {'MPH015'}:
            output.append(line_end)
    new_source = ''.join(output)
    if new_source == source:
        return False
    if show:
        print(new_source.rstrip())
    if not dry_run:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(new_source)
    return True


def strip_repeated_comments(filepath, dry_run=False, show=False):
    """MPH021: Remove lines containing comments that repeat 4+ non-whitespace chars."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        lines = f.readlines()
    new_lines = []
    changed = False
    for line in lines:
        if '#' not in line:
            new_lines.append(line)
            continue
        # Extract comment part (everything after the first '#')
        _, _, comment_rest = line.partition('#')
        # Check for 4+ identical non-whitespace characters in the comment itself
        if re.search(r'(\S)\1{3,}', comment_rest):
            changed = True
            continue  # Remove the entire cluttered comment line
        new_lines.append(line)
    new_source = ''.join(new_lines)
    if not changed:
        return False
    if show:
        print(new_source.rstrip())
    if not dry_run:
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_source)
    return True


def run():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Trim intentional leading underscores and excessive '
                    'blank lines from Python scripts generated by LLMs.',
    )
    parser.add_argument('files', nargs='+', help='List of .py files to process.')
    parser.add_argument('--remove-underscores', '--underscores',
                        action='store_true', default=False, dest='und_s')
    parser.add_argument('--remove-blank-lines', '--blanks',
                        action='store_true', default=False, dest='blank_s')
    parser.add_argument('--blank-lines-gap', type=int, default=3)
    parser.add_argument('--fix', action='store_true',
                        help='Actually make changes. Default is to show diff.')
    parser.add_argument('--show', action='store_true',
                        help='Show file contents if modified (default: '
                        'print affected files only).')
    parser.add_argument('--rules', type=str, default='',
                        help='Comma-separated rule codes (e.g. MPH001,MPH012).'
                             ' Overrides shorthands.')
    args = parser.parse_args()

    cli_raw = set()
    if args.rules:
        for r in args.rules.replace(';', ',').split(','):
            t = r.strip().upper()
            if t:
                try:
                    entry = lookup(t)
                    cli_raw.add((entry.get('code') or t).upper())
                except ValueError as exc:
                    print(f'Error: {exc}', file=sys.stderr)
                    sys.exit(2)
    if not cli_raw and (args.und_s or args.blank_s):
        und_codes = expand_shorthand('underscores') or ('MPH001', 'MPH002',
                                                        'MPH003')
        blk_codes = expand_shorthand('blanks') or ('MPH011', 'MPH012',
                                                   'MPH013', 'MPH014',
                                                   'MPH015')
        if args.und_s:
            cli_raw.update(und_codes)
        if args.blank_s:
            cli_raw.update(blk_codes)
    # Fallback to pyproject.toml / tox.ini when no CLI flags given at all.
    if not cli_raw:
        cfg_path = str(Path(__file__).resolve().parent.parent)
        try:
            resolved_cfg = resolve_rules(cli_raw, cfg_path) or set()
        except Exception:
            resolved_cfg = set()
        tox_cfg = (getattr(_rules_mod, 'rules_from_tox', lambda p: None)(cfg_path) or
                   set()) if hasattr(_rules_mod, 'rules_from_tox') else set()
        if resolved_cfg or tox_cfg:
            cli_raw = (resolved_cfg | tox_cfg)
    effective_rules = validate_rules(cli_raw)

    if not effective_rules:
        return  # Nothing to do.
    changed = False
    und_codes_all = expand_shorthand('underscores') or ('MPH001', 'MPH002',
                                                        'MPH003')
    blk_codes_all = expand_shorthand('blanks') or ('MPH011', 'MPH012',
                                                   'MPH013', 'MPH014',
                                                   'MPH015')
    cmt_rules_active = {'MPH021'}  # Explicit code for repeated comment removal

    for filepath in args.files:
        if not str(filepath).endswith('.py'):
            continue
        try:
            und_active = effective_rules & set(und_codes_all)
            blk_active = effective_rules & set(blk_codes_all)
            cmt_active = effective_rules & cmt_rules_active

            if und_active:
                if strip_underscores(Path(filepath), und_active,
                                     not args.fix, args.show):
                    print(f'MPH001-003 – stripped leading underscores '
                          f'from {filepath}')
                    changed = True
            if blk_active:
                if fix_blanks(Path(filepath), blk_active,
                              args.blank_lines_gap, not args.fix, args.show):
                    rule_list = ','.join(sorted(blk_active))
                    print(f'{rule_list} – stripped excessive blanks '
                          f'from {filepath}')
                    changed = True
            if cmt_active:
                if strip_repeated_comments(Path(filepath), not args.fix,
                                           args.show):
                    rule_list = ','.join(sorted(cmt_active))
                    print(f'{rule_list} – stripped cluttered comments '
                          f'from {filepath}')
                    changed = True
        except Exception:
            import traceback as _tb
            print(f'Failed to process {filepath}: ', file=sys.stderr)
            _tb.print_exc(file=sys.stderr)
    sys.exit(1 if changed else 0)


if __name__ == '__main__':
    run()
