"""Rule codes for manthey-precommit-hooks."""
from __future__ import annotations

import configparser
import tomllib
from pathlib import Path

# ---------------------------------------------------------------------------
# Rule catalogue -----------------------------------------------------------
RULE_CATALOG: dict[str, dict[str, str]] = {
    'MPH001': {'group': 'underscores', 'desc': 'Strip single leading underscores from modules-level variables.'},
    'MPH002': {'group': 'underscores', 'desc': 'Strip single leading underscores from top-level functions.'},
    'MPH003': {'group': 'underscores', 'desc': 'Strip single leading underscores from methods.'},
    'MPH011': {'group': 'blanks', 'desc': 'Collapse multiple consecutive blanks before def/class/decorator.'},
    'MPH012': {'group': 'blanks', 'desc': 'Enforce minimum code-line gap between blanks.'},
    'MPH013': {'group': 'blanks', 'desc': 'Preserve blank lines separating import blocks.'},
    'MPH014': {'group': 'blanks', 'desc': 'Preserve blank lines when outdenting from blocks.'},
    'MPH015': {'group': 'blanks', 'desc': 'Normalize trailing blank lines at end of file.'},
}

GROUPS: dict[str, tuple[str, ...]] = {
    'underscores': ('MPH001', 'MPH002', 'MPH003'),
    'blanks': ('MPH011', 'MPH012', 'MPH013', 'MPH014', 'MPH015'),
}


def lookup(code: str) -> dict[str, str]:
    """Validate code and return metadata; raises ValueError on unknown codes."""
    normed = code.upper()
    entry = RULE_CATALOG.get(normed)
    if not entry:
        avail = ', '.join(sorted(RULE_CATALOG.keys()))
        raise ValueError(f"Unknown rule code '{code}'. Available: {avail}")
    return dict(entry, code=normed)


def expand_shorthand(name: str) -> tuple[str, ...]:
    """Expand a shorthand string (e.g. 'blanks') into its corresponding codes."""
    clean = name.replace('-', '').lower()
    codes = GROUPS.get(clean)
    if not codes:  # type: ignore[unreachable]
        raise ValueError(f"Unknown shorthand '{name}'. Valid: {list(GROUPS.keys())}")
    return tuple(codes)


# ---------------------------------------------------------------------------
# Resolution helpers --------------------------------------------------------

def rules_from_pyproject(path: str | Path) -> set[str] | None:
    """Read *[tool.trim-underscores.rules]* from pyproject.toml."""
    toml_path = Path(path) / 'pyproject.toml'
    if not toml_path.is_file():
        return None
    with open(toml_path, 'rb') as fh:
        cfg = tomllib.load(fh)
    section = (cfg.get('tool', {}) or {}).get('trim-underscores')
    if not isinstance(section, dict):
        return None
    found: set[str] = set()

    raw_rules = section.get('rules')
    if isinstance(raw_rules, list):
        for item in raw_rules:
            if isinstance(item, str):
                entry = lookup(item)
                found.add(entry['code'])  # type: ignore[typeddict-item]
    elif isinstance(raw_rules, str):
        if ',' in raw_rules or ';' in raw_rules:
            for token in raw_rules.replace(';', ',').split(','):
                token = token.strip().upper()
                if token:
                    entry = lookup(token)
                    found.add(entry['code'])  # type: ignore[typeddict-item]
        else:
            try:
                found.update(expand_shorthand(raw_rules))
            except ValueError:
                entry = lookup(raw_rules)
                found.add(entry['code'])  # type: ignore[typeddict-item]
    for key in GROUPS:
        val = section.get(key)
        if not val:
            continue
        if isinstance(val, bool) and val:
            found.update(expand_shorthand(key))
        elif isinstance(val, str):
            try:
                found.update(expand_shorthand(val))
            except ValueError:
                entry = lookup(val)
                found.add(entry['code'])  # type: ignore[typeddict-item]
    return found or None


def rules_from_tox(path: str | Path) -> set[str] | None:
    """Read *[trim-underscores]* section from tox.ini (legacy config)."""
    ini_path = Path(path) / 'tox.ini'
    if not ini_path.is_file():
        return None
    cp = configparser.ConfigParser()
    cp.read(str(ini_path))

    sec_name = 'trim-underscores'
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
                entry = lookup(token)
                found.add(entry['code'])  # type: ignore[typeddict-item]
            except ValueError:
                pass
    return found or None


def resolve_rules(cli_rules: set[str], path: str | Path = '.') -> set[str]:
    """Merge CLI rules with pyproject.toml / tox.ini fallback."""
    if cli_rules:
        validated: set[str] = set()
        for r in cli_rules:
            entry = lookup(r)
            validated.add(entry['code'])  # type: ignore[typeddict-item]
        return validated
    pyproj = rules_from_pyproject(path) or set()
    tox_cfg = rules_from_tox(path) or set()
    return (pyproj | tox_cfg) if (pyproj or tox_cfg) else set()


def validate_rules(rules: Iterable[str]) -> set[str]:  # noqa: F821
    """Validate and deduplicate a collection of rule codes."""
    validated: set[str] = set()
    for code in rules:
        entry = lookup(code)
        validated.add(entry['code'])  # type: ignore[typeddict-item]
    return validated
