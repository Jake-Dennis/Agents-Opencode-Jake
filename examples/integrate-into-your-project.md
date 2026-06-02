# Example: Integrate this collection into your project

## Option A — clone and symlink (Windows)

```powershell
# In your project root
git clone https://github.com/JakeP/Agents-Opencode-Jake.git
# Run the installer (creates symlinks to the global opencode config)
.\Agents-Opencode-Jake\setup.bat
```

The `setup.bat`:
- Creates `%USERPROFILE%\.config\opencode\` if missing
- Symlinks this `opencode.json` into the global config (so all projects share the agents)
- Creates a `.opencode\` structure in your project
- Runs `/graphify .` to build the knowledge graph

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
