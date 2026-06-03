# Agents-Opencode-Jake — Copy to your project

This folder contains everything you need to use the conductor + 13 subagents in **any** OpenCode project.

## Quick install

```cmd
:: 1. Copy this folder into your project root
xcopy /E /I dist\* your-project\
cd your-project

:: 2. Merge agents into your opencode.json
::    Copy the "agent": { ... } block from dist/opencode.json
::    into your project's opencode.json (or use dist/opencode.json as-is)

:: 3. Run setup
setup.bat

:: 4. Open in OpenCode
opencode .
/graphify .
```

## What's in here

| File | Purpose |
|------|---------|
| `opencode.json` | Standalone config with all 13 agents. Copy the `"agent"` block into your project's config, or use this file directly if you don't have one yet. |
| `AGENTS.md` | Agent workflow docs. Referenced by `instructions: ["AGENTS.md"]` in opencode.json. |
| `setup.bat` | Installs pre-commit hook, builds knowledge graph, creates .opencode structure. |
| `uninstall.bat` | Removes pre-commit hook, cleans up .opencode/ and graphify-out/. |
| `scripts/verify-plan.py` | Mechanical plan verification (mandatory conductor step 8). |
| `scripts/pre-commit` | Pre-commit hook: validates JSON, runs schema check, tests, and plan verification. |
| `.opencode/skills/graphify-agent-workflow/SKILL.md` | Graphify skill for knowledge graph queries. |
| `.opencode/plans/` | Plan storage (conductor creates/archives plans here). |
| `.opencode/decisions/` | Architecture Decision Records. |

## What you still need to do

1. **Merge `opencode.json`** — Your project may already have an `opencode.json`. Copy the `"agent"` block from `dist/opencode.json` into yours:

   ```json
   {
     "model": "opencode/deepseek-v4-flash-free",
     "instructions": ["AGENTS.md"],
     "agent": {
       "conductor": { ... },
       "builder": { ... },
       ...all 13 agents...
     }
   }
   ```

2. **First run** — After setup, open OpenCode and run `/graphify .` to build the project's knowledge graph, then `/setup-project` to finalize.

## Files you can ignore (already in .gitignore)

- `graphify-out/` — Auto-generated knowledge graph
- `__pycache__/` — Python cache
- `.opencode/node_modules/` — OpenCode runtime cache
