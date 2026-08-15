from __future__ import annotations

import configparser
import tomllib
from pathlib import Path

RULE_CATALOG: dict[str, dict[str, str]] = {
    'AR001': {'group': 'underscores',
              'desc': 'Strip single leading underscores from '
                       'modules-level variables.'},
    'AR002': {'group': 'underscores',
              'desc': 'Strip single leading underscores from '
                       'top-level functions.'},
    'AR003': {'group': 'underscores',
              'desc': 'Strip single leading underscores from methods.'},
    'AR041': {'group': 'underscores',
              'desc': 'Strip single leading underscores from '
                       'non-exported variables.'},
    'AR042': {'group': 'underscores',
              'desc': 'Strip single leading underscores from '
                       'non-exported functions and methods.'},
    'AR043': {'group': 'underscores',
              'desc': 'Strip single leading underscores from '
                       'methods in non-exported classes.'},
    'AR011': {'group': 'blanks',
              'desc': 'Remove blank lines before or after indent/'
                       'outdent statement boundaries.'},
    'AR012': {'group': 'blanks',
              'desc': 'Remove blank lines immediately before/after comments.'},
    'AR013': {'group': 'blanks',
              'desc': 'Remove blank lines when consecutive statements '
                       'at same indent are fewer than min_gap.'},
    'AR014': {'group': 'blanks',
              'desc': 'Remove blank lines between decorators and their '
                       'target function/class definition.'},
    'AR021': {'group': 'comments',
              'desc': 'Remove comment-only lines repeating 4+'
                       ' identical non-whitespace chars.'},
    'AR022': {'group': 'comments',
              'desc': 'Enforce max line length on comment-only '
                       'lines (error only, no auto-fix).'},
    'AR031': {'group': 'emojis',
              'desc': 'Remove emoji characters.'},
    'AR032': {'group': 'emojis',
              'desc': 'Replace decorative text with plain versions.'},
}
GROUPS: dict[str, tuple[str, ...]] = {
    'underscores': ('AR001', 'AR002', 'AR003'),
    'underscores-private': ('AR041', 'AR042', 'AR043'),
    'blanks': ('AR011', 'AR012', 'AR013', 'AR014'),
    'emojis': ('AR031', 'AR032'),
    'comments': ('AR021', 'AR022'),
}


def prefix_lookup(code: str) -> list[str]:
    """Return codes from RULE_CATALOG that start with the given prefix."""
    prefix = code.upper()
    return [k for k in RULE_CATALOG if k.startswith(prefix)]


def expand_codes(code: str) -> set[str]:
    """Expand a code (exact or prefix) into matching rule codes.

    'AR02' expands to {'AR021'},  'AR001' stays as {'AR001'},
    unknown raises ValueError.
    """
    normed = code.upper()
    # exact match first
    if normed in RULE_CATALOG:
        return {normed}
    prefixes = prefix_lookup(normed)
    msg: str
    if len(prefixes) == 1:
        return set(prefixes)
    if not prefixes:
        avail = ', '.join(sorted(RULE_CATALOG.keys()))
        msg = f"Unknown rule code '{code}'. Available: {avail}"
        raise ValueError(msg)
    return set(prefixes)


def lookup(code: str) -> dict[str, str]:
    """Validate code and return metadata; raises ValueError on unknown codes."""
    normed = code.upper()
    entry = RULE_CATALOG.get(normed)
    msg: str
    if not entry:
        avail = ', '.join(sorted(RULE_CATALOG.keys()))
        msg = f"Unknown rule code '{code}'. Available: {avail}"
        raise ValueError(msg)
    return dict(entry, code=normed)


def expand_shorthand(name: str) -> tuple[str, ...]:
    """Expand a shorthand string (e.g. 'blanks' or
    'underscores-private') into its corresponding codes.
    """
    clean = name.replace('-', '').lower()
    if clean in GROUPS:
        return GROUPS[clean]
    # Also try lowercase version preserving hyphens
    # i.e. underscores-private
    alt = name.lower()
    codes = GROUPS.get(alt)
    msg: str
    if not codes:  # type: ignore[unreachable]
        avail = list(GROUPS.keys())
        msg = f"Unknown shorthand '{name}'. Valid: {avail}"
        raise ValueError(msg)
    return tuple(codes)


def find_rules_from_section(raw_rules):
    found: set[str] = set()
    if isinstance(raw_rules, list):
        for item in raw_rules:
            if isinstance(item, str):
                found.update(expand_codes(item))
    elif isinstance(raw_rules, str):
        if ',' in raw_rules or ';' in raw_rules:
            for token in raw_rules.replace(';', ',').split(','):
                token = token.strip().upper()
                if token:
                    found.update(expand_codes(token))
        else:
            try:
                found.update(expand_shorthand(raw_rules))
            except ValueError:
                try:
                    found.update(expand_codes(raw_rules))
                except ValueError as exc:
                    avail = ', '.join(sorted(RULE_CATALOG.keys()))
                    msg = (
                        f"Unknown shorthand '{raw_rules}'. "
                        f'Valid: {list(GROUPS.keys())} Available: {avail}'
                    )
                    raise ValueError(msg) from exc
    return found


def read_pyproject_section(path):
    toml_path = Path(path) / 'pyproject.toml'
    if not toml_path.is_file():
        return None
    with open(toml_path, 'rb') as fh:
        cfg = tomllib.load(fh)
    section = (cfg.get('tool', {}) or {}).get('agent-reformat')
    if not isinstance(section, dict):
        return None
    return section


def read_tox_section(path):
    ini_path = Path(path) / 'tox.ini'
    if not ini_path.is_file():
        return None
    cp = configparser.ConfigParser()
    cp.read(str(ini_path))
    if 'agent-reformat' not in cp:
        return None
    return dict(cp['agent-reformat'])


def read_max_gap(cli_value, path='.'):
    """Resolve --blank-lines-gap from CLI or config files."""
    pyproj = read_pyproject_section(path)
    if pyproj is not None:
        val = pyproj.get('blank_lines_gap', pyproj.get('max-gap'))
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    tox_ini = read_tox_section(path)
    if tox_ini is not None:
        val = tox_ini.get('blank_lines_gap', tox_ini.get('max-gap'))
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return cli_value


def read_comment_max(cli_value, path='.'):
    """Resolve --comment-lines-max from CLI or config files."""
    pyproj = read_pyproject_section(path)
    if pyproj is not None:
        val = pyproj.get('comment_lines_max', pyproj.get('max-line-length'))
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    tox_ini = read_tox_section(path)
    if tox_ini is not None:
        val = tox_ini.get('comment_lines_max', tox_ini.get('max-line-length'))
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return cli_value


def rules_from_pyproject(path: str | Path) -> set[str] | None:
    """Read *[tool.agent-reformat.rules]* from pyproject.toml."""
    toml_path = Path(path) / 'pyproject.toml'
    if not toml_path.is_file():
        return None
    with open(toml_path, 'rb') as fh:
        cfg = tomllib.load(fh)
    section = (cfg.get('tool', {}) or {}).get('agent-reformat')
    if not isinstance(section, dict):
        return None
    found = find_rules_from_section(section.get('rules'))
    for key in GROUPS:
        val = section.get(key)
        if isinstance(val, bool) and val:
            found.update(expand_shorthand(key))
        elif isinstance(val, str):
            try:
                found.update(expand_shorthand(val))
            except ValueError:
                try:
                    found.update(expand_codes(val))
                except ValueError as exc_3x:
                    avail = ', '.join(sorted(RULE_CATALOG.keys()))
                    msg = (
                        f"Unknown shorthand '{val}'. "
                        f'Valid: {list(GROUPS.keys())} Available: {avail}'
                    )
                    raise ValueError(msg) from exc_3x
    return found or None


def rules_from_tox(path: str | Path) -> set[str] | None:
    """Read *[agent-reformat]* section from tox.ini."""
    ini_path = Path(path) / 'tox.ini'
    if not ini_path.is_file():
        return None
    cp = configparser.ConfigParser()
    cp.read(str(ini_path))
    sec_name = 'agent-reformat'

    if sec_name not in cp:
        return None
    section = cp[sec_name]
    raw = section.get('rules') or section.get('blank-lines') or section.get('underscores')
    if not raw:
        return None
    found: set[str] = set()
    for t in raw.replace(';', ',').split(','):
        token = t.strip().upper()
        if token:
            try:
                found.update(expand_codes(token))
            except ValueError:
                pass
    return found or None


def resolve_rules(cli_rules: set[str], path: str | Path = '.') -> set[str]:
    """Merge CLI rules with pyproject.toml / tox.ini fallback."""
    if cli_rules:
        validated: set[str] = set()
        for r in cli_rules:
            validated.update(expand_codes(r))
        return validated
    pyproj = rules_from_pyproject(path) or set()
    tox_cfg = rules_from_tox(path) or set()
    return (pyproj | tox_cfg) if (pyproj or tox_cfg) else set()


def validate_rules(rules: Iterable[str]) -> set[str]:  # noqa: F821
    """Validate and deduplicate a collection of rule codes."""
    validated: set[str] = set()
    for code in rules:
        try:
            validated.update(expand_codes(code))
        except ValueError:
            pass
    return validated


def get_rule_group(code: str) -> str:
    """Return the group name for a rule code from RULE_CATALOG."""
    return RULE_CATALOG.get(code, {}).get('group', 'custom')
