# Contributing to Agents-Opencode-Jake

Thank you for your interest! This document explains how the project is organized, how to contribute effectively, and what standards to follow.

## Project structure

```
Agents-Opencode-Jake/
├── opencode.json              # Main agent configuration (13 agents + conductor)
├── opencode.schema.json       # JSON Schema for opencode.json
├── AGENTS.md                  # Agent roster and workflow (project README)
├── CONTRIBUTING.md            # This file
├── global-setup.bat           # Global installation script (Windows)
├── setup.bat                  # Local installation script (Windows)
├── uninstall-global.bat       # Global uninstall script (Windows)
├── uninstall.bat              # Local uninstall script (Windows)
├── pytest.ini                 # Pytest configuration
├── .opencode/
│   ├── commands/              # Custom slash commands (setup-project, build)
│   ├── decisions/             # Architecture Decision Records (ADR-001..006)
│   ├── skills/                # Named skills (opencode-config-merge, plan-review, etc.)
│   ├── plans/                 # Active implementation plans
│   │   └── completed/         # Archived (verified) plans
│   ├── todo.md                # Conductor-managed task checklist
│   ├── jobs.md                # Subagent live-progress tracking
│   └── work-log.md            # Append-only work cycle history
├── scripts/
│   ├── pre-commit             # Git pre-commit hook (bash)
│   ├── install-hook.sh        # Installs the pre-commit hook
│   ├── verify-plan.py         # Mechanical plan verifier (Python)
│   └── global-setup.py        # Config merge logic (Python)
├── graphify-out/              # Auto-generated knowledge graph
└── tests/                     # Pytest test suite
```

## Development workflow

### 1. Understand the agent system

This project has 13 agents orchestrated by a **conductor**. The conductor follows a 14-step workflow (see AGENTS.md). Each subagent has a specific role:

- **Implementation** (write access): builder, tester, docs, debugger, refactor, perf
- **Read-only** (scoped write to jobs.md): planner, architect, reviewer, explorer, security
- **Special**: git (bash-only), conductor (full access)

### 2. Adding a new feature

1. **Create a plan** — write `.opencode/plans/plan-NNN-title.md` following the template in AGENTS.md
2. **Run `/build`** — the conductor will execute the plan layer by layer, dispatch subagents, build, test, verify, and archive
3. **Ensure all tests pass** — `python -m pytest`

### 3. Adding or modifying a skill

Skills live in `.opencode/skills/<name>/SKILL.md`. Each skill:

- Must start with frontmatter (`---\ndescription: ...\n---`)
- Must have a body ≤15000 chars
- Must have a unique name (not colliding with graphify)
- Is registered in `opencode.json` under the `skills` array

Add the skill reference to `opencode.json` and add a test to `tests/test_skills.py`.

### 4. Adding a subagent

1. Add the agent block to `opencode.json` with the correct permission model
2. Update `tests/test_agent_safety.py` if adding new agents
3. Add a `variant` field if the agent supports model variants
4. Run `python -m pytest tests/` to verify

### 5. Updating the pre-commit hook

The pre-commit hook lives in `scripts/pre-commit`. Install it with:

```bash
bash scripts/install-hook.sh
```

The hook runs:
1. JSON validity check
2. Schema validation
3. Pytest fast suite (4 test files + 120s timeout)
4. Plan verification for staged plans

To bypass: `git commit --no-verify`

### 6. Writing tests

- All tests go in `tests/`
- Use pytest; add `test_<module>.py` files
- Test naming: `test_T_<area>_<number>` for traceability
- Run the full suite: `python -m pytest`
- Fast suite (for pre-commit): see `scripts/pre-commit` check 3

### 7. Knowledge graph

This project uses graphify for persistent knowledge. After any significant change:

```
/graphify . --update
```

Query existing knowledge:
```
graphify query "what is the permission model?"
```

## Code standards

- **JSON**: All config files (`opencode.json`, `opencode.schema.json`) must be valid JSON
- **YAML**: No YAML in this project (prefer JSON or Markdown w/ frontmatter)
- **Python**: Target Python 3.11+. No external runtime dependencies beyond pytest and jsonschema
- **Windows .bat**: Use `setlocal enabledelayedexpansion`. No `::` comments inside parenthesized blocks (use `REM`). Quote all `set "VAR=..."` values.
- **Markdown**: Frontmatter for all command/skill files. Max 15000 chars for skill bodies.

## Making a commit

1. `git add` the relevant files
2. `git commit` runs the pre-commit hook automatically
3. If the hook blocks you, fix the issue, then retry (do NOT use `--no-verify` as first resort)
4. If the hook hangs on Windows, ensure Python is on PATH (use `py -3` launcher) — see `scripts/pre-commit` for Windows detection

## Architecture Decision Records

Significant decisions are recorded in `.opencode/decisions/adr-NNN-title.md`:

| ADR | Topic |
|-----|-------|
| 001 | JSON-only agent configuration |
| 002 | Global-setup merge strategy |
| 003 | Graphify auto-refresh |
| 004 | Agent roles and permissions |
| 005 | Path-scoped permission pattern |
| 006 | 3-file ownership split (todo/work-log/jobs) |

To propose a new ADR, create a file following the existing format and open a discussion.
