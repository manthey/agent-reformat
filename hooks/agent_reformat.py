#!/usr/bin/env python3
# /// script
# name = "agent_reformat"
# requires-python = ">=3.11"
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
read_max_gap = rules.read_max_gap
read_comment_max = rules.read_comment_max
NESTED_FUNC_KIND = 'nested_func'
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
MODULE_STRUCTURAL_PREFIXES = (
    'def ',   # function definition
    'class ',  # class definition
    '@',      # decorators
    'import ',  # import statement
    'from ',  # from...import
)


def find_pep723_block(source: str) -> tuple[int, int]:
    """Return (start_lineno, end_lineno) of PEP 723 block or (-1, -1) if not found.

    Returns 1-based line numbers.
    """
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '# /// script':
            end_lineno = -1
            for j in range(i + 1, len(lines)):
                j1 = j + 1  # 1-based
                if lines[j].strip() == '# ///':
                    end_lineno = j1
                    break
            return (i + 1, end_lineno)
    return (-1, -1)


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
    any_valid_code_found = False
    for raw in re.finditer(r'[A-Z]+\s*\d+', codes_text):
        token = raw.group(0).strip().replace(' ', '')
        try:
            expanded = set(expand_codes(token))
            code_set |= expanded
            any_valid_code_found = True
        except ValueError:
            # Invalid rule codes are ignored, we won't fall back to bare-noqa
            pass
    if not any_valid_code_found:
        return False  # Specific codes were asked for but none are valid -> no match
    return bool(code_set & rules)


def get_nested_func_parent_class(nested_name, nested_lineno, tree, class_is_public):
    """Find which public class contains this nested function using AST."""
    current_classes = []
    result = None

    def visit(node):
        nonlocal result
        if isinstance(node, ast.ClassDef):
            current_classes.append((node.name, len(current_classes)))
            for child in getattr(node, 'body', []):
                visit(child)
            current_classes.pop()
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for item in ast.walk(node):
                if hasattr(item, 'name') and hasattr(item, 'lineno'):
                    if item.name == nested_name and item.lineno == nested_lineno:
                        if current_classes:
                            containing_cls = current_classes[-1][0]
                            if class_is_public.get(containing_cls, False):
                                result = containing_cls
                        break
            if result:
                return
    for child in getattr(tree, 'body', []):
        visit(child)
        if result:
            break
    return result


def collect_nested_functions(tree):
    """Collect nested function names and line numbers."""
    result = []

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child_node in getattr(node, 'body', []):
                if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result.append((child_node.name, child_node.lineno))
                visit(child_node)
        elif isinstance(node, ast.ClassDef):
            for child_node in getattr(node, 'body', []):
                visit(child_node)
    for node in getattr(tree, 'body', []):
        visit(node)
    result.sort(key=lambda x: x[1])
    return result


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


def get_constant_value(node):
    """Extract string value from an AST node (for __all__ elements)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # handle older Python versions with ast.Str
    if hasattr(ast, 'Str') and isinstance(node, ast.Str):  # type: ignore[name-defined]
        return node.s  # type: ignore[attr-defined]
    return None


def collect_exported_names(tree):
    """Detect __all__ export list or infer from module structure.

    Returns a tuple of (is_explicitly_exported, exported_set).  If __all__ is
    defined: (True, set of names in __all__).  If no __all__: (False, None)
    meaning everything is implicitly exported
    """
    exports = set()
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            val = get_constant_value(elt)
                            if val is not None:
                                exports.add(val)
                    return True, exports
    # No __all__ found - everything at module level is implicitly exported
    return False, None


def collect_class_exports(tree):
    """Determine which top-level classes are public vs private.

    Returns dict: class_name -> bool (is_public)
    A class is considered non-exported if:
    - Its name starts with underscore (private by convention), OR
    - __all__ is defined and it's NOT in the list
    """
    all_defined, exported_set = collect_exported_names(tree)
    classes = {}
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.ClassDef):
            name = node.name
            # Names starting with underscore are non-exported by convention
            if name.startswith('_'):
                is_pub = False
            elif all_defined:
                is_pub = name in (exported_set or set())
            else:
                # No __all__ means everything is implicitly exported
                is_pub = True
            classes[name] = is_pub
    return classes


def is_public_name(name, all_defined, exported_set):
    """Check if a name is 'public' (has export exposure).

    If __all__ is defined, only items in it are public.
    If no __all__, everything at module level is implicitly public.
    """
    if all_defined:
        # __all__ is defined - only items in it are exported
        return name in (exported_set or set())
    # No __all__, everything at module level is implicitly exported
    return True


def is_protected(active_underscore_rules, source, usages, ident, kind, lineno):  # noqa: C901
    """Return True if identifier should NOT be stripped."""
    kept = False
    for r in active_underscore_rules:
        entry = lookup(r)
        g = entry.get('group') or ''
        code = (entry.get('code') or '').upper()
        if g in ('underscores', 'underscores-private'):
            if kind == 'variable' and code in ('AR001', 'AR041'):
                kept = True
            elif kind == 'function' and code in ('AR002', 'AR042'):
                kept = True
            elif kind == 'method' and code in ('AR003', 'AR043'):
                kept = True
            elif kind is NESTED_FUNC_KIND and code in ('AR004', 'AR044'):
                kept = True
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


def strip_underscores(filepath, rules, dry_run=False, show=False):  # noqa: C901
    """strip_underscores per AR001-AR044 rules. Returns violations."""
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
        # Track Attribute.attr accesses (e.g. self.helper -> helper usage)
        elif hasattr(node, 'attr') and isinstance(node.ctx, ast.Load):
            if isinstance(node.attr, str):
                usages.setdefault(node.attr, []).append(getattr(node, 'lineno', None))
    raw_defs = collect_definitions_by_type(tree)
    # Collect nested function definitions
    nested_defs = collect_nested_functions(tree)
    # Determine which rule groups are active
    old_underscore_codes = expand_shorthand('underscores') or (
        'AR001', 'AR002', 'AR003', 'AR004')
    new_underscore_codes = {'AR041', 'AR042', 'AR043', 'AR044'}
    active_old_rules = set(rules) & set(old_underscore_codes)
    active_new_rules = set(rules) & new_underscore_codes
    if not active_old_rules and not active_new_rules:
        return []
    # Collect export info for AR04x rules
    all_defined, exported_set = collect_exported_names(tree)
    class_is_public = collect_class_exports(tree)
    replacements = {}
    violations = []

    def get_rule_code(kind, use_new_rules):
        """Return the appropriate rule code for reporting."""
        codes = {'variable': ('AR001', 'AR041'),
                 'function': ('AR002', 'AR042'),
                 'method': ('AR003', 'AR043'),
                 NESTED_FUNC_KIND: ('AR004', 'AR044')}
        base, priv = codes[kind]
        return priv if use_new_rules else base

    def need_check_export_exposure(kind):
        """Return True if this kind needs export exposure checking."""
        # Methods always need check (need to know their containing class)
        # Variables/functions only if AR04x rules are active
        return kind == 'method' or bool(active_new_rules)
    for ident, kind, lineno in raw_defs:
        if not ident.startswith('_') or ident.startswith('__') or ident.endswith('_'):
            continue
        if usages.get(ident, 0) == 0:
            continue
        # Check export exposure for AR04x rules
        has_export_exposure = False
        if active_new_rules and need_check_export_exposure(kind):
            if kind in ('variable', 'function'):
                has_export_exposure = is_public_name(ident, all_defined, exported_set)
            elif kind == 'method':
                # Find containing class for this method
                def_line_idx = lineno - 1
                lines_before = source.splitlines()[:def_line_idx]
                for cls_name, pub in class_is_public.items():
                    if pub:  # Only check public classes
                        for line_text in lines_before:
                            class_def = f'class {cls_name}(' if '(' else f'class {cls_name}: '
                            # Check class matching properly
                            cls_prefix = f'class {cls_name}('
                            cls_sep = ' '
                            if (class_def.replace(cls_sep, '') in line_text or
                                    cls_prefix in line_text):
                                has_export_exposure = True
                                break
            # AR04x rules: skip if item has export exposure
            if has_export_exposure and not active_old_rules:
                continue
        elif has_export_exposure and active_old_rules:
            # Old rules can still strip non-exported items under AR04x
            pass
        # Check export exposure for AR04x rules and skip protected names
        if active_new_rules and not active_old_rules:
            if kind in ('variable', 'function'):
                if is_public_name(ident, all_defined, exported_set):
                    continue  # Exported  don't strip
            elif kind == 'method':
                cls_found = False
                for cn, pub in class_is_public.items():
                    if pub:
                        for lt in source.splitlines()[:lineno - 1]:
                            if (f'class {cn}(' in lt or
                                    f'class {cn}: ' in lt or
                                    f'class {cn}:' in lt):
                                cls_found = True
                                break
                if cls_found:
                    continue  # In public class  don't strip
        # Check noqa protection for all active underscore rules
        all_active_rules = active_old_rules | active_new_rules
        if is_protected(all_active_rules, source, usages, ident, kind, lineno):
            continue
        replacements[ident] = ident.lstrip('_')
        violations.append(
            (lineno, get_rule_code(kind, bool(active_new_rules and not active_old_rules))))
    # Process nested functions for AR004/AR044
    usages = {}  # lines per identifier (also tracks Attribute.attr)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            usages.setdefault(node.id, []).append(getattr(node, 'lineno', None))
        elif hasattr(node, 'attr') and isinstance(node.ctx, ast.Load):
            if isinstance(node.attr, str):
                usages.setdefault(node.attr, []).append(getattr(node, 'lineno', None))
    has_ar004 = 'AR004' in set(rules) & {'AR001', 'AR002', 'AR003', 'AR004'}
    has_ar044 = 'AR044' in set(rules) & {'AR041', 'AR042', 'AR043', 'AR044'}
    for ident, lineno in nested_defs:
        if not ident.startswith('_') or ident.startswith('__') or ident.endswith('_'):
            continue
        # Skip unused nested functions
        if usages.get(ident, 0) == 0:
            continue
        # For AR044: only strip when inside a non-exported class (or no parent
        # class with __all__)
        skip_for_ar044 = False
        if has_ar044 and not has_ar004:
            if all_defined:  # When __all__ is defined
                parent_cls = get_nested_func_parent_class(ident, lineno, tree,
                                                          collect_class_exports(tree))
                if parent_cls:  # Inside a public class - don't strip under AR044
                    skip_for_ar044 = True
            else:
                # No __all__ means everything is implicitly public
                skip_for_ar044 = True
        if not skip_for_ar044 and (has_ar004 or has_ar044):
            all_active_underscore_rules = set(rules) & {'AR001', 'AR002', 'AR003', 'AR004',
                                                        'AR041', 'AR042', 'AR043', 'AR044'}
            if not is_protected(all_active_underscore_rules, source, usages, ident,
                                'nested_func', lineno):
                replacements[ident] = ident.lstrip('_')
                code = 'AR004' if has_ar004 else 'AR044'
                violations.append((lineno, code))
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


def fix_blanks(filepath, rules, min_gap=3, dry_run=False, show=False):  # noqa: C901
    """Apply AR011-014 to clean up blank lines. Returns violations."""
    active_rules = set(rules) if rules else set()
    if not active_rules:
        return []
    with open(filepath, encoding='utf-8', newline='') as f:
        source = f.read()
    # Process blank line rules AR011 through AR014
    ar011_active = 'AR011' in active_rules
    ar012_active = 'AR012' in active_rules
    ar013_active = 'AR013' in active_rules
    ar014_active = 'AR014' in active_rules
    violations_found: list[tuple[int, str]] = []
    new_source: str = source
    if ar011_active:
        new_source, removed = fix_blanks_ar011(new_source)
        if removed:
            blocks = collapse_contiguous(removed)
            for first_idx in blocks:
                violations_found.append((first_idx + 1, 'AR011'))
    if ar012_active:
        new_source, removed = fix_blanks_ar012(new_source)
        if removed:
            blocks = collapse_contiguous(removed)
            for first_idx in blocks:
                violations_found.append((first_idx + 1, 'AR012'))
    if ar013_active:
        new_source, removed = fix_blanks_ar013(new_source, min_gap=min_gap)
        if removed:
            blocks = collapse_contiguous(removed)
            for first_idx in blocks:
                violations_found.append((first_idx + 1, 'AR013'))
    if ar014_active:
        new_source, removed = fix_blanks_ar014(new_source)
        if removed:
            blocks = collapse_contiguous(removed)
            for first_idx in blocks:
                violations_found.append((first_idx + 1, 'AR014'))
    changed = new_source != source
    if not dry_run and changed:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(new_source)
    if show and changed:
        print(new_source.rstrip())
    return violations_found


def get_indent_level(line: str) -> int:
    """Return the number of leading spaces/tabs in a line."""
    return len(line) - len(line.lstrip())


def is_module_level_structural_element(text: str) -> bool:
    """Return True if *text* looks like module-level structural element.

    Used by AR012 to avoid collapsing blanks around top-level defs/classes/comments.
    """
    stripped = text.strip()
    return any(stripped.startswith(prefix) for prefix in MODULE_STRUCTURAL_PREFIXES)


def collapse_contiguous(indices: set[int]) -> list[int]:
    """Collapse a set of contiguous indices into first-of-each-block."""
    if not indices:
        return []
    result = []
    for idx in sorted(indices):
        if not result or idx != result[-1] + 1:
            result.append(idx)
    return result


def fix_blanks_ar011(source: str) -> tuple[str, set[int]]:  # noqa: C901
    """AR011: Remove blank lines before/after indent/outdent transitions.

    Blank lines inside multi-line string literals are never removed (this rule
    is otherwise pure text-indent analysis and would otherwise corrupt string
    content -- the same guard AR012/AR013/AR014 apply).
    Returns (new_source, set_of_0based_blank_line_indices_removed).
    """
    source = source.replace('\r\n', '\n')
    lines = source.split('\n')
    if not lines:
        return source, set()
    non_blank_lines: list[tuple[int, int]] = []  # (line_index_in_lines, indent)
    for i, ln in enumerate(lines):
        if ln.strip():
            non_blank_lines.append((i, get_indent_level(ln)))
    if not non_blank_lines:
        return source, set()
    # Build list of scope entries from AST (if possible) for AR011 outdent
    # detection. We collect (def_line_1based, base_indent) for classes and
    # functions. If parsing fails (e.g., partial code), scopes will be empty
    # but indent entry logic still works correctly.
    scopes: list[tuple[int, int]] = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                lineno = getattr(node, 'lineno', None)
                if lineno is not None and 0 < lineno <= len(lines):
                    scopes.append((lineno, get_indent_level(lines[lineno - 1])))
    except SyntaxError:
        pass  # If parsing fails, continue without scope info
    to_remove: set[int] = set()
    for nbl_idx in range(len(non_blank_lines)):
        cur_lin, cur_indent = non_blank_lines[nbl_idx]
        prev_nbl = non_blank_lines[nbl_idx - 1] if nbl_idx > 0 else None
        next_nbl = non_blank_lines[nbl_idx + 1] if nbl_idx + 1 < len(non_blank_lines) else None
        if prev_nbl is not None:
            prev_lin, prev_indent = prev_nbl
            # INDENT ENTRY: blank lines before entering a new block
            if cur_indent > prev_indent:
                for b in range(prev_lin + 1, cur_lin):
                    if not lines[b].strip():
                        to_remove.add(b)
        if next_nbl is not None:
            next_lin, next_indent = next_nbl
            # OUTDENT EXIT: blank lines after exiting a block.
            # Only remove if we're NOT at module level (indent=0 preserves
            # section separators).
            should_remove = False
            if cur_indent > next_indent and next_indent != 0:
                # Find the innermost scope containing our current position
                cur_lin_1based = cur_lin + 1
                innermost_containing_scope = None
                for entry_lineno, entry_indent in scopes:
                    if entry_lineno < cur_lin_1based and cur_indent > entry_indent:
                        innermost_containing_scope = (entry_lineno, entry_indent)
                if innermost_containing_scope is not None:
                    should_remove = True
                    # Avoid removing blanks before def/class at lower indent.
                    for check_lineno, check_indent in scopes:
                        if check_indent == next_indent and check_lineno > cur_lin_1based + 1:
                            should_remove = False
                            break
            if should_remove:
                for b in range(cur_lin + 1, next_lin):
                    if not lines[b].strip():
                        to_remove.add(b)
    # Preserve trailing blanks (after the last non-blank line)
    last_nbl_lin = non_blank_lines[-1][0] if non_blank_lines else -1
    for i in range(len(lines) - 1, last_nbl_lin, -1):
        to_remove.discard(i)
    # Blank lines that are part of a multi-line STRING token are not
    # structural whitespace -- they are string content.  AR011 is pure
    # text-indent based, so guard it the same way AR012/AR013/AR014 do by
    # excluding every line covered by a string literal from to_remove.
    to_remove -= find_string_lines(source)
    new_lines = [ln for i, ln in enumerate(lines) if i not in to_remove]
    return '\n'.join(new_lines), to_remove


def fix_blanks_ar012(source: str) -> tuple[str, set[int]]:  # noqa: C901
    """AR012: Remove ALL blank lines immediately before/after comments.
    Uses tokenize to identify actual comment tokens (not # inside strings).
    Returns (new_source, set_of_0based_blank_line_indices_removed).
    """
    source = source.replace('\r\n', '\n')
    lines = source.split('\n')
    if not lines:
        return source, set()
    # Find real comment line numbers (1-based) using tokenize.
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return source, set()
    comment_lines: set[int] = set()   # 1-based line numbers containing real comments
    pep723_end_lineno = -1            # Track PEP 723 '///' end marker line number
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            lineno = tok.start[0]
            # Only consider lines where the comment is at start
            line_text = lines[lineno - 1] if lineno <= len(lines) else ''
            stripped = line_text.lstrip()
            if stripped.startswith('#'):
                # Skip PEP 723 block markers - preserve blank after '///'
                if stripped == '# ///':
                    pep723_end_lineno = lineno
                    continue
                # Skip shebang lines (#!) -- they are not regular comments
                if stripped.startswith('#!'):
                    continue
                comment_lines.add(lineno)
    # Collect import statement line numbers.
    # PEP8 requires two blank lines after module-level imports.
    import_lines: set[int] = set()
    import_end_lines: set[int] = set()  # end_lineno of imports to protect blanks
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                ln_start = getattr(node, 'lineno', None)
                if ln_start is not None:
                    import_lines.add(ln_start)
                ln_end = getattr(node, 'end_lineno', None)
                if ln_end is not None:
                    for l in range(ln_start, ln_end + 1):
                        import_end_lines.add(l)
    except SyntaxError:
        pass  # If parsing fails, just don't protect imports
    # Find last non-blank line index for preserving trailing blanks
    last_non_blank_idx = None
    inv_range = range(len(lines) - 1, -1, -1)
    for idx in inv_range:
        if lines[idx].strip():
            last_non_blank_idx = idx
            break
    if last_non_blank_idx is None:
        return source, set()  # All blank lines, no changes needed
    trailing_start = last_non_blank_idx + 2  # 1-based: line after last content + 1
    to_remove: set[int] = set()  # indices (0-based) of blank lines to remove
    for idx, line in enumerate(lines):
        if line.strip():  # not a blank line - skip
            continue
        # Don't touch trailing blanks at end of file
        # Convert to 1-based for consistency with comment_lines which is
        # 1-based
        blank_line_num = idx + 1  # 1-based line number of this blank line
        if blank_line_num >= trailing_start:
            continue
        # Preserve blank line immediately after PEP 723 '///' marker
        if pep723_end_lineno > 0 and idx == pep723_end_lineno - 1:  # convert back
            continue
        # Check if this blank line is IMMEDIATELY before a comment (next
        # non-blank is a comment) OR immediately after a comment (prev
        # non-blank was a comment)
        # We check ALL consecutive blanks that touch the boundary by looking at
        # the nearest content on either side
        # Look backward for preceding non-blank line number
        prev_content_line = None
        for p in range(idx - 1, -1, -1):
            if lines[p].strip():
                prev_content_line = p + 1  # 1-based
                break
        # Look forward for following non-blank line number
        next_content_line = None
        for n in range(idx + 1, len(lines)):
            if lines[n].strip():
                next_content_line = n + 1  # 1-based
                break
        # Protect blank lines after import statements (PEP8 requirement)
        if prev_content_line and (
            prev_content_line in import_lines or
            prev_content_line in import_end_lines
        ):
            continue
        # Also protect blanks BEFORE imports (e.g., comments before imports)
        if next_content_line and (
            next_content_line in import_lines or
            next_content_line in import_end_lines
        ):
            continue

        def is_shebang(lineno):
            """Check if lineno points to a shebang line."""
            if lineno and 0 < lineno <= len(lines):
                return lines[lineno - 1].lstrip().startswith('#!')
            return False
        # Preserve blank line immediately after a shebang
        if prev_content_line and is_shebang(prev_content_line):
            continue
        is_before_comment = (next_content_line and next_content_line in comment_lines)
        is_after_comment = (prev_content_line and prev_content_line in comment_lines)
        if is_before_comment or is_after_comment:
            # Protection against overzealous comment-adjacent blank removal.
            # If a highly indented comment (e.g. an inner function's
            # docstring/comment) touches structural spacing that belongs to the
            # outer scope, we must NOT collapse it.

            target_blank_indent = get_indent_level(line)  # indent of this specific blank line
            prev_lno = prev_content_line - 1 if prev_content_line else None
            next_lno = next_content_line - 1 if next_content_line else None
            prev_content_indent = get_indent_level(lines[prev_lno]) if prev_lno is not None else -1
            next_content_indent = get_indent_level(lines[next_lno]) if next_lno is not None else -1
            target_blank_indent = get_indent_level(line)
            prev_lno = prev_content_line - 1 if prev_content_line else None
            next_lno = next_content_line - 1 if next_content_line else None
            prev_content_indent = get_indent_level(lines[prev_lno]) if prev_lno is not None else -1
            next_content_indent = get_indent_level(lines[next_lno]) if next_lno is not None else -1
            skip_removal = False
            # Rule 1: Scope boundary protection. If this blank line is at a
            # lower indent (e.g. module level) but surrounds content that is
            # heavily indented (inner scope comments), it acts as an external
            # separator! Don't collapse it because of inner-scope rules.
            if (target_blank_indent < prev_content_indent and
                    target_blank_indent < next_content_indent):
                skip_removal = True
            # Rule 2: Multi-blank protection at same depth. Even if indents
            # match, never eat all consecutive blank lines in a row! PEP8
            # requires blanks around top-level defs/classes. This prevents
            # AR012 from collapsing entire module gaps into zero spacing.
            elif target_blank_indent == prev_content_indent == next_content_indent:
                prev_blank_adjacent = ((idx > 0) and not lines[idx - 1].strip())
                next_blank_adjacent = ((idx + 1 < len(lines)) and not lines[idx + 1].strip())
                if (prev_blank_adjacent or next_blank_adjacent):
                    skip_removal = True
            # Rule 3: Protect blank lines at module level.
            # If this blank is at indent=0 and both sides reach structural
            # elements, preserve spacing. Prevents incorrect removal between
            # modules.
            if not skip_removal and target_blank_indent == 0:
                # Look past comments/blanks for true structural elements
                prev_structural_line = None
                next_structural_line = None
                start_p = prev_lno if prev_lno is not None else idx - 1
                for p in range(start_p, -1, -1):
                    pline_text = lines[p] if p >= 0 else ''
                    if pline_text.strip():
                        # Skip non-structural. If line starts
                        if pline_text.lstrip().startswith('#'):
                            continue
                        if is_module_level_structural_element(pline_text):
                            prev_structural_line = p + 1
                            break
                start_n = next_lno if next_lno is not None else idx + 1
                for n in range(start_n, len(lines)):
                    nline_text = lines[n] if n < len(lines) else ''
                    if nline_text.strip():
                        # Skip non-structural. If line starts
                        if nline_text.lstrip().startswith('#'):
                            continue
                        if is_module_level_structural_element(nline_text):
                            next_structural_line = n + 1
                            break
                # Protect blanks when structural elements exist on both sides
                # this is section spacing between top-level constructs,
                # not inner-function whitespace.
                if prev_structural_line and next_structural_line:
                    skip_removal = True
            if not skip_removal:
                to_remove.add(idx)
    new_lines = [ln for i, ln in enumerate(lines) if i not in to_remove]
    return '\n'.join(new_lines), to_remove


STMT_TYPES_KW = (
    ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign,
    ast.AsyncFor, ast.AsyncWith, ast.For, ast.While,
    ast.With, ast.If, ast.Try, ast.Assert, ast.Return,
    ast.Break, ast.Continue, ast.Raise, ast.Import,
    ast.ImportFrom, ast.Delete, ast.Global, ast.Nonlocal,
    ast.ExceptHandler,
)


def find_string_lines(source):
    """Find 0-based line indices inside STRING tokens."""
    out = set()
    try:
        for tok in tokenize.generate_tokens(
            io.StringIO(source).readline,
        ):
            if tok.type == tokenize.STRING:
                for ln in range(tok.start[0], tok.end[0] + 1):
                    out.add(ln - 1)
    except (tokenize.TokenError, ValueError):
        pass
    return out


def collect_stmt_starts(source, lines, string_lines):  # noqa: C901
    """Walk AST and collect (line0, indent) for statement nodes.

    Also returns import_line_numbers to allow AR013 to protect blanks around imports.
    """
    tree = ast.parse(source)
    out: list[tuple[int, int]] = []
    import_lines: set[int] = set()  # 0-based line numbers that are imports
    # Build a set of (start_line_1based, end_line_1based) for truly multiline
    # STRING tokens. These mark actual multi-line string content ranges.
    multiline_string_ranges: list[tuple[int, int]] = []
    try:
        import tokenize as _tokenize  # type: ignore[import-untyped]
        for tok in _tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == _tokenize.STRING:
                start_ln = tok.start[0]  # 1-based
                end_ln = tok.end[0]     # 1-based
                if end_ln > start_ln:   # only multi-line
                    multiline_string_ranges.append((start_ln, end_ln))
    except ValueError:
        pass  # If tokenization fails, just don't protect any ranges

    def visit(node):
        if isinstance(node, STMT_TYPES_KW):
            ln = getattr(node, 'lineno', None)
            if ln is not None:
                ln0 = ln - 1
                # Skip statements that fall INSIDE a multi-line STRING range.
                # We use actual token boundaries (start_line..end_line) rather
                # than fixed offset checks to avoid false positives where:
                #   - the statement's own arguments are STRING literals
                #     (e.g., events.bind('data.process', ...))
                #   - adjacent statements happen to use STRING arguments
                in_multiline = False
                for s, e in multiline_string_ranges:
                    if s <= ln0 + 1 <= e:  # 1-based check
                        in_multiline = True
                        break
                skip = in_multiline
                if not skip:
                    out.append((ln0, get_indent_level(lines[ln0])))
                    # Track import statements separately
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        import_lines.add(ln0)
        for child in getattr(node, '_fields', ()):
            val = getattr(node, child, None)
            if isinstance(val, ast.AST):
                visit(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, ast.AST):
                        visit(item)
    visit(tree)
    return out, import_lines


def find_protected_blanks(source, tree):
    """Find blank line indices that must be preserved."""
    lines = source.split('\n')
    protected: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef,
                                 ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        # Preserve the blank lines directly above the definition, starting
        # from its first decorator when one is present (the AST lineno is
        # the 'def'/'class' keyword line, not the first decorator line).
        # Blanks before a def/class are structural separators, so they must
        # not be removed (e.g., between a class attribute and a decorated
        # method).
        top_0 = node.lineno - 1  # 0-based index of the def/class keyword
        for dec in getattr(node, 'decorator_list', ()):
            dec_ln = getattr(dec, 'lineno', None)
            if dec_ln is not None and dec_ln - 1 < top_0:
                top_0 = dec_ln - 1
        idx = top_0 - 1
        while idx >= 0 and not lines[idx].strip():
            protected.add(idx)
            idx -= 1
        end_ln = getattr(node, 'end_lineno', None)
        if end_ln is None:
            continue
        end_0 = end_ln - 1
        for blank_i in range(end_0 + 1, len(lines)):
            if lines[blank_i].strip():
                break
            protected.add(blank_i)
    last_idx: int | None = None
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip():
            last_idx = idx
            break
    if last_idx is not None:
        for i in range(last_idx + 1, len(lines)):
            protected.add(i)
    return protected


def group_same_indent(stmts, lines):
    """Group consecutive same-indent (line0, indent) pairs."""
    groups: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    for entry in stmts:
        line0, indent = entry
        if not cur or indent != cur[-1][1]:
            if cur:
                groups.append(cur)
            cur = [(line0, indent)]
        else:
            cur.append((line0, indent))
    if cur:
        groups.append(cur)
    return groups


def count_contiguous_before(group, si):
    """Count consecutive (by line number) entries in group ending at position si."""
    if si == 0:
        return 1
    base_line = group[si][0]
    count = 1
    for j in range(si - 1, -1, -1):
        if group[j][0] == base_line - (si - j):
            count += 1
        else:
            break
    return count


def count_contiguous_after(group, si):
    """Count consecutive (by line number) entries in group starting from position si."""
    base_line = group[si][0]
    count = 1
    for j in range(si + 1, len(group)):
        if group[j][0] == base_line + (j - si):
            count += 1
        else:
            break
    return count


def remove_empty_for_short_groups(groups_by_indent, min_gap, lines, protected):
    """Return blank line indices to remove for statement groups/pairs.

    Processes two types of removals:
      1. Short groups (< min_gap entries): all internal blanks removed
      2. Pairs within large groups where BOTH sides have < min_gap contiguous
         statements: those specific blank lines are removed.
    """
    to_remove: set[int] = set()
    for grp_entries in groups_by_indent:
        if len(grp_entries) < min_gap:  # Short group - process all pair gaps
            for si in range(len(grp_entries) - 1):
                line_a, _ = grp_entries[si]
                line_b, _ = grp_entries[si + 1]
                for blank_idx in range(line_a + 1, line_b):
                    if (lines[blank_idx].strip() == '' and
                            blank_idx not in protected):
                        to_remove.add(blank_idx)
        else:  # Large group - check each pair's gaps using contiguous stmt counts
            for si in range(len(grp_entries) - 1):
                line_a, _ = grp_entries[si]
                line_b, _ = grp_entries[si + 1]
                gap_lines = list(range(line_a + 1, line_b))
                if not gap_lines:
                    continue
                # Count contiguous statements on each side of THIS gap
                before_count = count_contiguous_before(grp_entries, si)
                after_count = count_contiguous_after(grp_entries, si + 1)
                # Check for blanks in the gap (excluding protected ones)
                blanks_in_gap = [
                    idx for idx in range(line_a + 1, line_b)
                    if lines[idx].strip() == '' and idx not in protected
                ]
                if not blanks_in_gap:
                    continue
                # If either side 003c min_gap, remove all blanks in gap
                # If NOT (both sides minimal), preserve one blank separator
                if before_count < min_gap and after_count < min_gap:
                    # Remove all blanks in this gap
                    to_remove.update(blanks_in_gap)
                else:
                    # Otherwise keep first blank as separator, remove rest.
                    for i, idx in enumerate(blanks_in_gap):
                        if i > 0:
                            to_remove.add(idx)
    return to_remove


def fix_blanks_ar014(source) -> tuple[str, set[int]]:  # noqa: C901
    """AR014: Remove blank lines between decorators and their target.

    Removes ALL consecutive blank lines that appear:
    - Between a decorator line and the next (another decorator or target)
    - After the last decorator and its function/class definition

    Preserved (not removed):
    - Blank lines inside multi-line strings (verified via tokenize).
    - Module-level structural separators unrelated to decorators.
    - File trailing blanks after last content.
    """
    source = source.replace('\r\n', '\n')
    lines = source.split('\n')
    if not lines:
        return source, set()
    # Find all blank line indices to remove for AR014
    to_remove: set[int] = set()
    # Step 1: Get AST tree and find target function/class line numbers
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, set()
    target_lines_1based: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ln = getattr(node, 'lineno', None)
            if ln is not None:
                target_lines_1based.add(ln)
    # Step 2: Find decorator lines via tokenize
    try:
        tok_list = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return source, set()
    string_lines = find_string_lines(source)
    # Collect 1-based line numbers of actual @ decorators (not in strings)
    dec_line_set: set[int] = set()
    for tok in tok_list:
        if tok.type == tokenize.OP and tok.string == '@':
            ln = tok.start[0]
            if ln not in string_lines:
                dec_line_set.add(ln)
    # Step 3: For each target, find its decorator block.
    # Walk backward from the line before target, skipping blanks, collecting
    # @ lines.
    for tline in sorted(target_lines_1based):
        if tline <= 1:
            continue
        decs_block: list[int] = []
        check_ln = tline - 1  # start from line right before target
        while check_ln > 0:
            if check_ln in string_lines:
                break
            if check_ln in dec_line_set:
                decs_block.append(check_ln)
                check_ln -= 1
            elif not lines[check_ln - 1].strip():
                # Blank line - skip it, might still be part of decor block
                check_ln -= 1
            else:
                break
        if not decs_block:
            continue
        decs_block.reverse()  # sort ascending
        if not decs_block:
            continue
        first_dec_ln = min(decs_block)   # earliest @ in decorator block
        # Remove blank lines in range [first_dec_ln, tline)
        # Convert to 0-based for line list access
        for ln_1based in range(first_dec_ln, tline):
            idx_0based = ln_1based - 1
            if not (0 <= idx_0based < len(lines)):
                continue
            # Skip non-blank lines (they're real content)
            if lines[idx_0based].strip():
                continue
            to_remove.add(idx_0based)
    new_lines = [ln for i, ln in enumerate(lines) if i not in to_remove]
    return '\n'.join(new_lines), to_remove


def fix_blanks_ar013(source, min_gap=3):
    """AR013: Remove blank lines when < min_gap statements at same indent.

    Blanks preserved: end-of-file; between def/class blocks;
    inside multi-line strings; around import statements.
    Returns (new_source, set_of_0based_blank_line_indices_removed).
    """
    source = source.replace('\r\n', '\n')
    lines = source.split('\n')
    if len(lines) <= 1:
        return source, set()
    string_lines = find_string_lines(source)
    tree = ast.parse(source)
    stmts_raw, import_lines = collect_stmt_starts(source, lines, string_lines)
    deduped: list[tuple[int, int]] = sorted(
        set(stmts_raw), key=lambda e: e[0],
    )
    if len(deduped) < 2:
        return source, set()
    protected = find_protected_blanks(source, tree)
    # Blank lines inside multi-line strings are not real blank lines and
    # must never be removed, even if they fall between two statements.
    protected.update(string_lines)
    # Protect blank lines around import statements - blanks before/after
    # imports
    for imp_ln in import_lines:
        # A blank line before the import (between previous statement and
        # import)
        if imp_ln > 0 and not lines[imp_ln - 1].strip():
            protected.add(imp_ln - 1)
        # A blank line after the import (between import and next statement)
        if imp_ln + 1 < len(lines) and not lines[imp_ln + 1].strip():
            protected.add(imp_ln + 1)
    groups_by_indent = group_same_indent(deduped, lines)
    to_remove = remove_empty_for_short_groups(
        groups_by_indent, min_gap, lines, protected,
    )
    new_lines = [
        ln for idx, ln in enumerate(lines) if idx not in to_remove
    ]
    return '\n'.join(new_lines), to_remove


def is_emoji_char(c):
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


def check_comment_line_length(filepath, rules, max_len=79):
    """AR022: Check comment-only lines against max line length. Error only."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    if 'AR022' not in rules:
        return []
    # We parse the entire token stream to strictly distinguish real comments
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return []
    violations = []  # line numbers (1-based)
    seen_lines = set()
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            lineno = tok.start[0]
            if lineno in seen_lines:
                continue
            lines = source.split('\n')
            line_text = lines[lineno - 1]
            # A comment-only line: the entire stripped content is a comment
            stripped = line_text.strip()
            if stripped.startswith('#') and len(stripped) > 1:
                # Only flag if the *entire* meaningful content is comments
                # (i.e., no code before the # on that line)
                hash_pos = line_text.find('#')
                if hash_pos >= 0 and not line_text[:hash_pos].strip():
                    if len(line_text.rstrip()) > max_len:
                        violations.append(lineno)
                        seen_lines.add(lineno)
    return violations


def strip_emojis(filepath, rules, dry_run=False, show=False):
    """AR031/AR032: Remove emojis and replace decorative text. Returns violations.

    Each fix is gated by its own rule: emoji removal runs only when AR031
    is active, decorative-text replacement only when AR032 is active, so a
    file is never silently mutated by a rule the caller did not request.
    """
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    violations = []
    new_source = source
    # Decorative-text replacements (AR032) - replace before emoji removal
    if 'AR032' in rules:
        deco_replacements = {
            '\u2713': '+',   # check mark to plain +
            '\u2717': 'x',   # ballot X to plain x
            '\u2718': 'x',   # heavy ballot X to plain x
        }
        replaced = new_source
        for deco_char, repl in deco_replacements.items():
            replaced = replaced.replace(deco_char, repl)
        if replaced != new_source:
            for i, line in enumerate(source.splitlines(), 1):
                if any(dc in line for dc in deco_replacements):
                    violations.append((i, 'AR032'))
            new_source = replaced
    # Remove emoji characters
    if 'AR031' in rules:
        removed = ''.join('' if is_emoji_char(c) else c for c in new_source)
        if removed != new_source:
            for i, old_line in enumerate(new_source.splitlines(), 1):
                if has_genuine_emoji(old_line):
                    violations.append((i, 'AR031'))
            new_source = removed
    changed = new_source != source
    if changed:
        if show:
            print(new_source.rstrip())
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8', newline='') as fw:
                fw.write(new_source)
    return violations


def strip_repeated_comments(filepath, rules=frozenset(), dry_run=False, show=False):
    """AR021: Remove lines with repeated-char comments. Returns line nums."""
    file_path = Path(filepath)
    with open(file_path, encoding='utf-8', newline='') as f:
        source = f.read()
    pep723 = find_pep723_block(source)
    # We parse the entire token stream to strictly distinguish real comments
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return []
    violations = []  # line numbers (1-based)
    seen_lines = set()
    # Iterate the global token stream: we only care if a line's first
    # meaningful token is a COMMENT.
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            lineno = tok.start[0]
            if lineno in seen_lines:
                continue
            lines = source.split('\n')
            line_text = lines[lineno - 1]
            if has_noqa(line_text, rules):
                seen_lines.add(lineno)
                continue
            # Extract the comment content based on token position
            start_col = tok.start[1] + 1  # +1 for the '#' itself
            comment_part = line_text[start_col - 1:]
            # Check for repetition of ANY non-whitespace character that isn't
            # a hexadecimal digit
            if re.search(r'([^ \t\r\n\f\v0-9a-fA-F])\1{3,}', comment_part):
                # Skip comments within PEP 723 block
                if pep723[0] > 0 and pep723[0] <= lineno <= pep723[1]:
                    seen_lines.add(lineno)
                    continue
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


def process_file(args, filepath, effective_rules, und_codes_all,
                 und_private_codes_all,
                 blk_codes_all, cmt_rules_active, emj_codes_all,
                 gap=3, comment_len=79):
    """Run all active rules on a file and report violations to stdout."""
    und_active = effective_rules & set(und_codes_all)
    und_private_active = effective_rules & set(und_private_codes_all)
    # Merge underscore rules before passing to strip_rules
    all_underscore_rules = und_active | und_private_active
    blk_active = effective_rules & set(blk_codes_all)
    cmt_active = effective_rules & cmt_rules_active
    emj_active = effective_rules & set(emj_codes_all)
    changed = False
    violations_reported = []
    if all_underscore_rules:
        for lineno, rule_code in strip_underscores(
            Path(filepath), all_underscore_rules, not args.fix, args.show,
        ):
            violations_reported.append(
                (lineno, f'{rule_code} ({get_rule_group(rule_code)})'),
            )
    if blk_active:
        for lineno, rule_code in fix_blanks(
            Path(filepath), blk_active,
            gap, not args.fix, args.show,
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
    # AR022 is error-only (no auto-fix)
    ar022_active = bool(effective_rules & {'AR022'})
    if ar022_active:
        for ln in check_comment_line_length(
            Path(filepath), effective_rules, comment_len,
        ):
            violations_reported.append(
                (ln, 'AR022 (comments)'),
            )
    # Print all violations in standard pre-commit format
    if violations_reported:
        changed = True
        for lineno, desc in sorted(violations_reported):
            print(f'{filepath}:{lineno}: {desc}')
    return changed


def run(cli_args=None):
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
    parser.add_argument('--comment-lines-max', type=int, default=79)
    parser.add_argument('--fix', action='store_true',
                        help='Actually make changes. Default is to show diff.')
    parser.add_argument('--show', action='store_true',
                        help='Show file contents if modified (default: '
                        'print affected files only).')
    parser.add_argument('--rules', type=str, default='',
                        help='Comma-separated rule codes (e.g. AR001,AR012). '
                             'Pass "AR" to enable all rules. Overrides shorthands.')
    args = parser.parse_args(cli_args)
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
    # If no rules are specified anywhere, enable ALL rules by default.
    if not effective_rules:
        effective_rules = validate_rules(expand_codes('AR'))
    changed = False
    und_codes_all = set(expand_shorthand('underscores'))
    und_private_codes_all = set(expand_shorthand('underscores-private'))  # AR041-3
    blk_codes_all = set(expand_shorthand('blanks'))
    emj_codes_all = set(expand_shorthand('emojis'))
    cmt_rules_active = {'AR021'}
    cfg_path = '.'
    # Resolve config options from pyproject.toml / tox.ini
    gap = read_max_gap(args.blank_lines_gap, cfg_path)
    comment_len = read_comment_max(args.comment_lines_max, cfg_path)
    for filepath in args.files:
        if not str(filepath).endswith('.py'):
            continue
        changed = process_file(
            args, filepath, effective_rules, und_codes_all, und_private_codes_all,
            blk_codes_all, cmt_rules_active, emj_codes_all,
            gap=gap, comment_len=comment_len) or changed
    sys.exit(1 if changed else 0)


if __name__ == '__main__':
    run()
