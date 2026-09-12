# agent-reformat

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pre-commit hooks for cleaning up AI/LLM-generated code.

## Overview

This repository provides custom [pre-commit](https://pre-commit.com/) hooks that help clean up common artifacts left behind when using LLMs or AI pair programmers:

### Hooks Included

- **`agent-reformat`** - Reformats standard artifacts (e.g., excessive underscores, blank lines) from generated code.

## Rule System

The hook exposes individual rule codes for granular control. Specific rules can be selected via CLI args or config files.

### Error Message Format

Violations are reported in standard pre-commit format:

```
filepath:line: CODE Message — Fix hint
```

Example output:
```
myfile.py:42: AR022 Comment line exceeds maximum length [144>79 chars] — Split into multiple shorter comment lines or rewrap.
myfile.py:15: AR002 Leading underscore on top-level function — Remove the leading underscore: `def _func()` → `def func()`
```

Each violation includes:
- **File and line number** for easy navigation
- **Rule code** (e.g., AR022) for reference
- **Clear message** describing what's wrong
- **Actionable fix hint** telling you exactly how to fix it

For AR022 (comment line length), the message includes the actual length vs. maximum (e.g., `144>79 chars`).

### Available Rules

| Code   | Feature      | Description                                                                 | Fix Hint |
|--------|--------------|-----------------------------------------------------------------------------|----------|
| `AR001` | Underscore   | Strip single leading underscores from **module-level variables**.           | `_var` → `var` |
| `AR002` | Underscore   | Strip single leading underscores from **top-level functions**.              | `def _func()` → `def func()` |
| `AR003` | Underscore   | Strip single leading underscores from **class methods**.                    | `def _method(self)` → `def method(self)` |
| `AR004` | Underscore   | Strip single leading underscores from **nested functions**.                 | Remove leading underscore from nested function |
| `AR011` | Blank lines  | Remove blank lines before indent/outdent statement boundaries.              | Indentation already shows structure; extra blanks are noise |
| `AR012` | Blank lines  | Remove blank lines immediately adjacent to comments.                        | Comments should be adjacent to the code they describe |
| `AR013` | Blank lines  | Remove blank lines when consecutive statements at same indent < min_gap.    | Blank lines only for logical sections, not between every statement |
| `AR014` | Blank lines  | Remove blank lines between decorators and their target.                     | Decorators must be directly above their target |
| `AR021` | Comments     | Remove comment-only lines repeating 4+ identical chars.                     | Decorative separators (e.g., `#####`) are noise |
| `AR022` | Comments     | Enforce max line length on **comment-only** lines (error only, no auto-fix). | Split into multiple shorter lines or rewrap |
| `AR031` | Emojis       | Remove emoji characters.                                                    | Emojis are not appropriate in source code |
| `AR032` | Emojis       | Replace decorative text with plain versions.                                | Replace ✓, ✗ with +, x |
| `AR041` | Underscore   | Strip underscores from **non-exported variables**.                          | Variable not in `__all__`; remove underscore |
| `AR042` | Underscore   | Strip underscores from **non-exported functions/methods**.                  | Not exported; remove underscore |
| `AR043` | Underscore   | Strip underscores from methods in **non-exported classes**.                 | Class not exported; remove underscore |
| `AR044` | Underscore   | Strip underscores from **non-exported nested functions**.                   | Not exported; remove underscore |

The **AR00x** rules strip single leading underscores from identifiers regardless of export status. These are safe for application code that isn't a library with an explicit public API.

The **AR04x** rules only strip single leading underscores from identifiers that are **not exported** via `__all__` or have public exposure. This is preferred for libraries to signal what functions, methods, and variables are official or quasi-hidden.

The rationale behind the **AR01x** rules is directly from PEP8: "Use blank lines in functions, sparingly, to indicate logical sections.". Coding agents clearly do know what the word "sparingly" means. For logical sections, indents, outdents, and comments already indicate this, and having gaps between every statement becomes meaningless.

### Default Behavior

If no rules are specified via CLI arguments or configuration files (`pyproject.toml`, `tox.ini`), _all_ available rules are enabled by default. This behavior is equivalent to passing `--rules=AR`, which expands all rule codes (AR*) for maximum cleanup coverage against LLM-generated code artifacts.

### Activation Methods

**CLI**:
```bash
agent-reformat --rules AR001,AR012 path/to/files.py
```

**`.pre-commit-config.yaml`**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/manthey/agent-reformat
    rev: v1.0.0
    hooks:
      - id: agent-reformat
        args: [ --rules, AR001,AR011 ]
```

### Configuration

In `pyproject.toml`:
```toml
[tool.agent-reformat]
rules = ["AR011", "AR012"]  # list of rule codes

# Configuration options (also via tox.ini):
blank_lines_gap = 3         # min gap between blank lines (AR013)
comment_lines_max = 79      # max length for comment-only lines (AR022)
```

In `tox.ini`:
```ini
[agent-reformat]
; Comma-separated rule codes only (shorthands not supported)
rules = AR014,AR015

; Configuration options:
blank_lines_gap = 3         ; min gap between blank lines (AR013)
comment_lines_max = 79      ; max length for comment-only lines (AR022)
