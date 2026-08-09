#!/usr/bin/env python3
# /// script
# name = "agent_reformat"
# requires-python = ">=3.9"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

try:
    from . import rules as rules  # pip / tests / -m
except ImportError:  # standalone CLI
    parent = str(Path(__file__).resolve().parent.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import hooks.rules as rules

lookup = rules.lookup
expand_shorthand = rules.expand_shorthand
validate_rules = rules.validate_rules
resolve_rules = rules.resolve_rules
expand_codes = rules.expand_codes
get_rule_group = rules.get_rule_group

SUPP_EMOJI_RANGES = [
    (0x1F300, 0x1F9FF),  # Misc symbols, emoticons, transport
    (0x1FA00, 0x1FAFF),  # Chess, shapes, symbols extended
    (0x1F000, 0x1F02F),  # Games
    (0x1F0A0, 0x1F0FF),  # Playing cards
]
BMP_PATTERNS = [
    '\u2600-\u27BF',       # Misc symbols, dingbats
    '\uFE00-\uFE0F',       # Variation selectors
    '\u2460-\u24FF',       # Circled letters
    '\u2500-\u259F',       # Box drawing, block elements
    '\u2190-\u21FF',       # Arrows
    '\uFE0F',              # Variation selector 16
    '\u2610\u2611\u2612',  # Checkboxes
    '\u25C9\u25CB\u25CF',  # Radio-button bullets
    '\u25B6\u25B7\u25BA',  # Decorative arrow bullets
    '\u2022\u2023\u2043',  # Fancy bullets
]
bmp_re = re.compile('|'.join(f'[{p}]' for p in BMP_PATTERNS))


def has_noqa(line, rules=frozenset()):
    """Return True if line has a proper # noqa directive for any of rules.

    A "proper" directive: ``# noqa`` (bare), ``# noqa AR0XX``, or
    ``# noqa:[AR0XX]``. Does NOT match comments that just contain the word
    "noqa" in regular prose.
    """
    hash_pos = line.find('#')
    if hash_pos < 0:
        return False
    # Look for "noqa" at start of comment text (with optional whitespace)
    after_hash = line[hash_pos + 1:]
    noqa_m = re.match(r'\s*(?i:noqa)(.*)$', after_hash, re.IGNORECASE)
    if not noqa_m:
        return False
    after_noqa = noqa_m.group(1).strip()

    # Empty or whitespace-only after noqa = bare "skip all"
    if not after_noqa:
        return True
    # Strip leading colon/bracket chars before examining content
    cleaned = re.sub(r'^[ :\[]+', '', after_noqa).rstrip(' ]')

    # Check for bracket syntax or code-like text
    if ']' in cleaned and cleaned.index(']') > 0:
        codes_text = cleaned[:cleaned.index(']')]
    elif re.match(r'[A-Z][A-Z\s\d]*', cleaned, re.IGNORECASE):
        codes_text = cleaned
    else:
        # Text doesn't look like codes -> bare noqa
        return True
    if not codes_text.strip():
        return True
    code_set = frozenset()
    for raw in re.finditer(r'[A-Z]+\s*\d+', codes_text):
        token = raw.group(0).strip().replace(' ', '')
        try:
            code_set |= set(expand_codes(token))
        except ValueError:
            pass
    return bool(code_set & rules) if code_set else True


def collect_definitions_by_type(tree):
    """Return list of (ident, kind, lineno) tuples scoped to module-level only."""
    result = []
    for node in getattr(tree, 'body', []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append((node.name, 'function', node.lineno))
        elif isinstance(node, ast.ClassDef):
            for inner_node in getattr(node, 'body', []):
                if isinstance(inner_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result.append((inner_node.name, 'method', inner_node.lineno))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = getattr(node, 'targets', []) or [getattr(node,
                                                               'target', None)]
            for tgt in targets:
                if tgt and isinstance(tgt, ast.Name):
                    result.append((tgt.id, 'variable', node.lineno))
    return result


def is_protected(active_underscore_rules, source, usages, ident, kind, lineno):
    """Return True if identifier should NOT be stripped."""
    kept = False
    for r in active_underscore_rules:
        entry = lookup(r)
        g = entry.get('group') or ''
        code = (entry.get('code') or '').upper()
        if g == 'underscores':
            if kind == 'variable' and code == 'AR001':
                kept = True
            elif kind == 'function' and code == 'AR002':
                kept = True
            elif kind == 'method' and code == 'AR003':
                kept = True
    if not kept:
        return False  # Not a candidate for stripping at all
    lines = source.splitlines()
    def_line_lineno = lineno - 1
    if 0 <= def_line_lineno < len(lines):
        if has_noqa(lines[def_line_lineno], active_underscore_rules):
            return True
    if usages.get(ident):
        for ln in usages[ident]:
            if ln is None:
                continue
            if 0 <= ln - 1 < len(lines):
                if has_noqa(lines[ln - 1], active_underscore_rules):
                    return True
    return False


def strip_underscores(filepath, rules, dry_run=False, show=False):
    """Strip underscores per AR001-003 rules. Returns list of (lineno, ident) for violations."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    usages = {}       # lines per identifier
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            usages.setdefault(node.id, []).append(getattr(node, 'lineno', None))
    raw_defs = collect_definitions_by_type(tree)
    replacements = {}

    underscore_codes = expand_shorthand('underscores') or (
        'AR001', 'AR002', 'AR003')
    active_underscore_rules = set(rules) & set(underscore_codes)
    if not active_underscore_rules:
        return []
    violations = []
    for ident, kind, lineno in raw_defs:
        if not ident.startswith('_') or ident.startswith('__') or ident.endswith('_'):
            continue
        if usages.get(ident, 0) == 0:
            continue
        if is_protected(active_underscore_rules, source, usages, ident, kind, lineno):
            continue
        replacements[ident] = ident.lstrip('_')
        violations.append(
            (lineno, {'variable': 'AR001', 'function': 'AR002', 'method': 'AR003'}[kind]))
    if not violations:
        return []
    new_source = source
    for old, new in sorted(replacements.items(), key=len, reverse=True):
        pattern = r'\b' + re.escape(old) + r'\b'
        new_source = re.sub(pattern, new, new_source)
    if show:
        print(new_source.rstrip())
    if not dry_run:
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(new_source)
    return violations


def fix_blanks(filepath, rules, min_gap=3, dry_run=False, show=False):  # noqa
    """Apply AR011-015 to clean up blank lines. Returns violations."""
    active_rules = set(rules) if rules else set()

    with open(filepath, encoding='utf-8', newline='') as f:
        source = f.read()
    line_end = '\r\n' if '\r\n' in source else '\n'
    lines = source.splitlines(keepends=True)
    output = []
    violations = []  # (lineno, rule_code) per blank line to remove
    pending_blank = False
    code_lines_since_blank = 0
    consecutive_blanks = 0
    prev_indent = 0
    prev_text = ''
    indent_cause = {0: 'other'}
    gap = min_gap

    for idx, line in enumerate(lines):
        curr_text = line.strip()
        curr_lineno = idx + 1
        curr_indent = len(line) - len(line.lstrip())

        if not curr_text:
            pending_blank = True
            consecutive_blanks += 1
            continue
        outdented_to_top = curr_indent == 0 and prev_indent > 0

        if pending_blank:
            has_many = consecutive_blanks >= 2
            write_pep8_two = False
            curr_has_noqa = has_noqa(line, active_rules) and not curr_text.startswith(' ')

            if ('AR011' in active_rules and has_many and
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
                    'AR013' in active_rules and ((pi and not ci) or
                                                 (pi and ci)))
                keep_for_outdent = False
                if 'AR014' in active_rules and prev_indent > curr_indent:
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
                elif curr_has_noqa:
                    should_keep = True
                if write_pep8_two:
                    pass
                elif outdented_to_top and has_many:
                    output.append(line_end + line_end)
                    violations.extend((curr_lineno - consecutive_blanks + i, 'AR011')
                                      for i in range(consecutive_blanks))
                elif should_keep:
                    # Record AR012 violation for blank lines kept due to gap rule
                    if gap_reached and same_indent and 'AR012' in active_rules:
                        violations.extend((curr_lineno - consecutive_blanks + i, 'AR012')
                                          for i in range(consecutive_blanks))
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
        elif active_rules & {'AR015'}:
            violations.extend((idx - consecutive_blanks + i, 'AR015')
                              for i in range(consecutive_blanks))
            output.append(line_end)
    new_source = ''.join(output)
    changed = new_source != source
    if changed and violations:
        if show:
            print(new_source.rstrip())
        if not dry_run:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(new_source)
        return violations
    if changed:
        # Changes made but no specific blank violations (e.g. indentation changes)
        if show:
            print(new_source.rstrip())
        if not dry_run:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(new_source)
        return []
    return []


def is_emoji_char(c):
    """Check if a character matches emoji ranges (excluding deco text)."""
    cp = ord(c)
    # Decorative text chars are NOT emojis per user spec
    if cp in (0x2713, 0x2717, 0x2718):
        return False
    # Supplementary-plane ranges
    for lo, hi in SUPP_EMOJI_RANGES:
        if lo <= cp <= hi:
            return True
    # BMP patterns
    return bool(bmp_re.match(c))


def has_genuine_emoji(line_text):
    """Return True if line contains actual emoji (not only deco-text)."""
    for c in line_text:
        cp = ord(c)
        if cp >= 0x10000:
            for lo, hi in SUPP_EMOJI_RANGES:
                if lo <= cp <= hi:
                    return True
        elif bmp_re.match(c):
            # BMP match: check if it's deco text (not emoji) or genuine emoji
            if cp not in (0x2713, 0x2717, 0x2718):
                return True
    return False


def strip_emojis(filepath, rules, dry_run=False, show=False):
    """AR031/AR032: Remove emojis and replace decorative text. Returns violations."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    # Decorative-text replacements (AR032) - replace before emoji removal
    deco_replacements = {
        '\u2713': '+',   # check mark to plain +
        '\u2717': 'x',   # ballot X to plain x
        '\u2718': 'x',   # heavy ballot X to plain x
    }
    new_source = source
    for deco_char, repl in deco_replacements.items():
        new_source = new_source.replace(deco_char, repl)
    # Remove emoji characters
    removed = ''.join(
        '' if is_emoji_char(c) else c for c in new_source
    )

    changed = removed != source
    violations = []
    if changed:
        if 'AR031' in rules:
            old_lines = source.splitlines()
            for i, old_line in enumerate(old_lines, 1):
                if has_genuine_emoji(old_line) and i <= len(removed.splitlines()):
                    if removed.splitlines()[i - 1] != old_line:
                        violations.append((i, 'AR031'))
        if 'AR032' in rules:
            for i, line in enumerate(source.splitlines(), 1):
                if any(dc in line for dc in deco_replacements):
                    violations.append((i, 'AR032'))
        if show:
            print(removed.rstrip())
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8', newline='') as fw:
                fw.write(removed)
    return violations


def strip_repeated_comments(filepath, rules=frozenset(), dry_run=False, show=False):
    """AR021: Remove lines with cluttered repeated-char comments. Returns line nums."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    # We parse the entire token stream to strictly distinguish real comments
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenizeError:
        return []
    violations = []  # line numbers (1-based)
    seen_lines = set()

    # Iterate the global token stream: we ONLY care if a line's first meaningful token is a COMMENT.
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            lineno = tok.start[0]
            if lineno in seen_lines:
                continue
            lines = source.split('\n')
            line_text = lines[lineno - 1]

            # Check for "" directive (skip if present)
            if has_noqa(line_text, rules):
                seen_lines.add(lineno)
                continue
            # Extract the comment content based on token position
            start_col = tok.start[1] + 1  # +1 for the '#' itself
            comment_part = line_text[start_col - 1:]

            # Check for repetition of ANY non-whitespace character (letters, digits, or symbols)
            if re.search(r'(\S)\1{3,}', comment_part):
                violations.append(lineno)
                seen_lines.add(lineno)
    # Apply removals
    lines = source.split('\n')
    new_source = '\n'.join(line for i, line in enumerate(lines, 1) if i not in violations)

    changed = (new_source != source)
    if changed:
        if show:
            print(new_source.rstrip())
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_source)
        return violations
    return []


def process_file(args, filepath, effective_rules, und_codes_all,
                 blk_codes_all, cmt_rules_active, emj_codes_all):
    """Run all active rules on a file and report violations to stdout."""
    und_active = effective_rules & set(und_codes_all)
    blk_active = effective_rules & set(blk_codes_all)
    cmt_active = effective_rules & cmt_rules_active
    emj_active = effective_rules & set(emj_codes_all)
    changed = False
    violations_reported: list[tuple[int, str]] = []
    if und_active:
        for lineno, rule_code in strip_underscores(
            Path(filepath), und_active, not args.fix, args.show,
        ):
            violations_reported.append(
                (lineno, f'{rule_code} ({get_rule_group(rule_code)})'),
            )
    if blk_active:
        for lineno, rule_code in fix_blanks(
            Path(filepath), blk_active,
            args.blank_lines_gap, not args.fix, args.show,
        ):
            violations_reported.append(
                (lineno, f'{rule_code} ({get_rule_group(rule_code)})'),
            )
    if emj_active:
        for lineno, rule_code in strip_emojis(
            Path(filepath), effective_rules, not args.fix, args.show,
        ):
            violations_reported.append(
                (lineno, f'{rule_code} ({get_rule_group(rule_code)})'),
            )
    if cmt_active:
        for ln in strip_repeated_comments(
            Path(filepath), effective_rules, not args.fix, args.show,
        ):
            violations_reported.append((ln, 'AR021 (comments)'))
    # Print all violations in standard pre-commit format
    if violations_reported:
        changed = True
        for lineno, desc in sorted(violations_reported):
            print(f'{filepath}:{lineno}: {desc}')
    return changed


def run():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Reformat excessive artifacts from generated Python code.',
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
                        help='Comma-separated rule codes (e.g. AR001,AR012). '
                             'Pass "AR" to enable all rules. Overrides shorthands.')
    args = parser.parse_args()

    cli_raw = set()
    if args.rules:
        for r in args.rules.replace(';', ',').split(','):
            t = r.strip().upper()
            if t:
                try:
                    cli_raw.update(expand_shorthand(t.lower()))
                except ValueError:
                    cli_raw.update(expand_codes(t))
    if not cli_raw and (args.und_s or args.blank_s):
        und_codes = set(expand_shorthand('underscores'))
        blk_codes = set(expand_shorthand('blanks'))
        if args.und_s:
            cli_raw.update(und_codes)
        if args.blank_s:
            cli_raw.update(blk_codes)
    # Fallback to pyproject.toml / tox.ini when no CLI flags given at all.
    if not cli_raw:
        cfg_path = str(Path(__file__).resolve().parent.parent)
        resolved_cfg = resolve_rules(cli_raw, cfg_path) or set()
        tox_cfg = (getattr(rules, 'rules_from_tox', lambda p: None)(cfg_path) or
                   set()) if hasattr(rules, 'rules_from_tox') else set()
        if resolved_cfg or tox_cfg:
            cli_raw = (resolved_cfg | tox_cfg)
    effective_rules = validate_rules(cli_raw)

    # If no rules are specified anywhere (CLI or config), enable ALL rules by default.
    if not effective_rules:
        effective_rules = validate_rules(expand_codes('AR'))
    changed = False
    und_codes_all = set(expand_shorthand('underscores'))
    blk_codes_all = set(expand_shorthand('blanks'))
    emj_codes_all = set(expand_shorthand('emojis'))
    cmt_rules_active = {'AR021'}

    for filepath in args.files:
        if not str(filepath).endswith('.py'):
            continue
        changed = changed or process_file(
            args, filepath, effective_rules, und_codes_all, blk_codes_all,
            cmt_rules_active, emj_codes_all)
    sys.exit(1 if changed else 0)


if __name__ == '__main__':
    run()
