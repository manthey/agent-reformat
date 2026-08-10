# manthey-precommit-hooks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pre-commit hooks for cleaning up AI/LLM-generated code.

## Overview

This repository provides custom [pre-commit](https://pre-commit.com/) hooks that help clean up common artifacts left behind when using LLMs or AI pair programmers:

### Hooks Included

- **`agent-reformat`** - Reformats standard artifacts (e.g., excessive underscores, blank lines) from generated code.

## Rule System

The hook exposes individual rule codes for granular control. You can activate specific, all, or none of the rules via CLI args or config files.

### Available Rules

| Code   | Feature      | Description                                                                 |
|--------|--------------|-----------------------------------------------------------------------------|
| `AR001` | Underscore   | Strip single leading underscores from **module-level variables**.           |
| `AR002` | Underscore   | Strip single leading underscores from **top-level functions**.              |
| `AR003` | Underscore   | Strip single leading underscores from **class methods**.                    |
| `AR011` | Blank lines  | Collapse multiple consecutive blanks before `def`/`class`/`@` (PEP-8 E302). |
| `AR012` | Blank lines  | Enforce minimum code-line gap between blanks otherwise.                     |
| `AR013` | Blank lines  | Preserve blank lines that separate import blocks from other code.            |
| `AR014` | Blank lines  | Preserve blank lines when outdenting from a `def`/`class` block.            |
| `AR015` | Blank lines  | Normalize trailing blank lines at end of file (PEP-8 E305/E306).           |
| `AR016` | Blank lines  | Remove blank lines surrounding comments.                                    |
| `AR021` | Comments     | Remove comment-only lines repeating 4+ identical non-whitespace chars.      |
| `AR022` | Comments     | Enforce max line length on **comment-only** lines (error only, no auto-fix). Lines exceeding the configured maximum must be manually rewrapped by users or agents into shorter multi-line comments or shortened entirely.          |
| `AR031` | Emojis       | Remove emoji characters.                                                    |
| `AR032` | Emojis       | Replace decorative text with plain versions.                                |

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
  - repo: https://github.com/manthey/manthey-precommit-hooks
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
blank_lines_gap = 3         # min gap between blank lines (AR012)
comment_lines_max = 79      # max length for comment-only lines (AR022)
```

In `tox.ini`:
```ini
[agent-reformat]
; Comma-separated rule codes only (shorthands not supported)
rules = AR014,AR015

; Configuration options:
blank_lines_gap = 3         ; min gap between blank lines (AR012)
comment_lines_max = 79      ; max length for comment-only lines (AR022)
