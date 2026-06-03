# Agents-Opencode-Jake — Copy to your project

This folder contains everything you need to use the conductor + 13 subagents in **any** OpenCode project.

## Quick start

```cmd
:: 1. Copy this folder into your project root
xcopy /E /I path\to\Agents-Opencode-Jake\dist\* your-project\
cd your-project

:: 2. Run setup — installs everything
setup.bat

:: 3. Open in OpenCode
opencode .
/graphify .
```

That's it. `setup.bat` copies AGENTS.md, the agent config, scripts, skill, creates `.opencode/` structure, installs the pre-commit hook, and builds the knowledge graph — all from a single command.

## What's in here

| File | Purpose |
|------|---------|
| `opencode.json` | Standalone config with all 13 agents. |
| `AGENTS.md` | Agent workflow docs. Referenced by `instructions: ["AGENTS.md"]` in opencode.json. |
| `setup.bat` | **Run this.** Installs everything into your project. |
| `global-setup.bat` | **Global** install: symlinks agents/skills into `%USERPROFILE%\.config\opencode\`. |
| `uninstall.bat` | Removes local setup (hook, .opencode/, graphify-out/). |
| `uninstall-global.bat` | Removes global setup (symlinks, config). |
| `scripts/verify-plan.py` | Mechanical plan verification (mandatory conductor step 8). |
| `scripts/pre-commit` | Pre-commit hook: validates JSON, runs schema check, tests, and plan verification. |
| `.opencode/skills/graphify-agent-workflow/SKILL.md` | Graphify skill for knowledge graph queries. |
| `.opencode/plans/` | Plan storage (conductor creates/archives plans here). |
| `.opencode/decisions/` | Architecture Decision Records. |

## Files you can ignore (already in .gitignore)

- `graphify-out/` — Auto-generated knowledge graph
- `__pycache__/` — Python cache
- `.opencode/node_modules/` — OpenCode runtime cache
