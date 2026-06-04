# Example: Integrate this collection into your project

## Option A — clone and symlink (Windows)

```powershell
# In your project root
git clone https://github.com/JakeP/Agents-Opencode-Jake.git
# Run the local installer
.\Agents-Opencode-Jake\setup.bat
```

The `setup.bat` (local only — no global side effects):
- Copies `AGENTS.md` and the `graphify-agent-workflow` skill into the project
- Merges the 13-agent `opencode.json` into the project's own `opencode.json`
- Creates `.opencode\` structure (plans, decisions, todo, work-log)
- Initializes git, writes a `.gitignore`, installs the pre-commit hook
- Runs `/graphify .` to build the knowledge graph

Re-running `setup.bat` on an existing project also refreshes the `graphify` skill and plugin. When pip is ahead of the installed stamp, the installer prints `[2b/7] Checking graphify version...` and prompts `graphify A.B.C installed, pip has X.Y.Z. Refresh? (Y/n):` (default `Y`). `--unattended` auto-upgrades; `--dry-run` previews.

## Global install (all projects on this machine)

If you want the agents available to every opencode project, run `global-setup.bat` from the cloned repo. It **merges** the *entire* project's `opencode.json` into `%USERPROFILE%\.config\opencode\opencode.jsonc` — idempotently — and **symlinks** the `graphify-agent-workflow` skill. The merge covers:

- 13 agents (`agent.<name>`)
- 3 scalars (`default_agent`, `model`, `small_model`)
- `skills.paths` (union + dedupe)
- `instructions` (union + dedupe, plus the repo's `AGENTS.md`)
- `command` (slash commands — `/setup-project`, `/build`)
- `mcp` (graphify MCP server)
- `provider` + `enabled_providers` (AI provider config)
- `permission` (the project family's permission policy)
- `$schema` (the schema URL pointer)

The installer writes a manifest at `%USERPROFILE%\.config\opencode\.opencode-jake-installed.json` so `uninstall-global.bat` can surgically remove every contribution and restore your pre-install `provider` / `permission` values from a snapshot.

Flags: `--unattended`, `--dry-run`, `--force` (env vars: `GLOBAL_SETUP_YES=1`, `GLOBAL_SETUP_DRY_RUN=1`, `GLOBAL_SETUP_FORCE=1`).

Re-running `global-setup.bat` auto-refreshes the `graphify` pip package, the user-scope skill file, and the project-scope plugin. When pip is ahead of the stamp at `~/.config/opencode/skills/graphify/.graphify_version`, the installer prints `[4b/5] Checking graphify version...` and prompts `(Y/n)`.

```powershell
# Non-interactive (skip the y/N prompt):
echo y | .\Agents-Opencode-Jake\global-setup.bat --unattended
set GLOBAL_SETUP_YES=1 && .\Agents-Opencode-Jake\global-setup.bat
:: Verify, then undo if needed:
opencode agent list
.\Agents-Opencode-Jake\uninstall-global.bat --unattended
```

## Option B — copy `opencode.json` only

If you don't want to clone the whole repo:

```powershell
# In your project root
Copy-Item path\to\Agents-Opencode-Jake\opencode.json .
# Optionally copy the docs
Copy-Item path\to\Agents-Opencode-Jake\AGENTS.md -Optional
```

Then add to your `opencode.json` `instructions` array:
```json
{
  "instructions": [
    "AGENTS.md"
  ]
}
```

## Option C — for testing, symlink just the .opencode/skills

If you already have your own `opencode.json` and just want graphify skill access:

```powershell
# In your project root
New-Item -ItemType Directory -Force -Path .opencode\skills
# Use a junction (works without admin)
New-Item -ItemType Junction -Path .opencode\skills\graphify-agent-workflow -Target path\to\Agents-Opencode-Jake\.opencode\skills\graphify-agent-workflow
```

## Verify it works

```powershell
opencode agent list
# Should show: build, plan, conductor, planner, builder, architect, reviewer, tester, docs, debugger, refactor, git, explorer, security, perf
```

Then start a session and try:
```
/setup-project    # initialize the project
/graphify .       # build the knowledge graph
/build            # run any plans in .opencode/plans/
```

## What you get

- 13 agents (1 conductor, 1 planner, 11 specialists)
- 2 custom commands (`/setup-project`, `/build`)
- graphify MCP server (query the knowledge graph from any agent)
- 645+ test checks
- A persistent `.opencode/` audit trail (work-log, plans, decisions)

## See also

- `README.md` — top-level overview
- `AGENTS.md` — agent descriptions
- `LICENSE` — MIT
