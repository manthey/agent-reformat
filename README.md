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
|--------|-------------|-----------------------------------------------------------------------------|
| `AR001` | Underscore  | Strip single leading underscores from **module-level variables**.           |
| `AR002` | Underscore  | Strip single leading underscores from **top-level functions**.              |
| `AR003` | Underscore  | Strip single leading underscores from **class methods**.                    |
| `AR011` | Blank lines | Collapse multiple consecutive blanks before `def`/`class`/`@` (PEP-8 E302). |
| `AR012` | Blank lines | Enforce minimum code-line gap between blanks otherwise.                     |
| `AR013` | Blank lines | Preserve blank lines that separate import blocks from other code.            |
| `AR014` | Blank lines | Preserve blank lines when outdenting from a `def`/`class` block.            |
| `AR015` | Blank lines | Normalize trailing blank lines at end of file (PEP-8 E305/E306).           |

### Shorthands

The existing shorthands are expanded to their constituent rules:

- `--underscores` → `AR001,AR002,AR003`
- `--blanks` → `AR011,AR012,AR013,AR014,AR015`

### Activation Methods

**CLI (highest priority)**: `--rules AR001,AR012`
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/manthey/manthey-precommit-hooks
    hooks:
      - id: agent-reformat
        args: [ --rules, AR001,AR011 ]
```

**Shorthands**: `--underscores` and `--blanks` flags (expanded per the table above).

**pyproject.toml** (fallback when no CLI flags are given):
```toml
[tool.agent-reformat]
rules = ["AR011", "AR012"]
# or use booleans for full group activation:
blanks = true
```

**tox.ini** (legacy fallback, only used when pyproject.toml doesn't provide anything):
```ini
[agent-reformat]
rules = AR014,AR015
blank-lines = true  # or: underscores = true
```

## Installation & Usage

### As a Local Pre-commit Hook in Your Repository

Add this repository as a local hook reference in your project's `.pre-commit-config.yaml`:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/manthey/manthey-precommit-hooks
    rev: v1.0.0
    hooks:
      - id: agent-reformat
        args:
          - --underscores
          - --blanks
```

Then run pre-commit to install and test:

```bash
pre-commit install
pre-commit run --all-files
```

### Standalone Usage

You can also run the hook script directly for one-time cleanup:

```bash
python hooks/agent_reformat.py --remove-underscores --remove-blank-lines path/to/file1.py path/to/file2.py
```

Or with individual rule codes:

```bash
python hooks/agent_reformat.py --rules AR003,AR011,AR012 path/to/*.py
```
