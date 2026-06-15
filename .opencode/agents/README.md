# Agents — Copy-and-Paste Bundle

This folder is a **complete, self-contained agent set**. Drop it into any project that reads `.md` files as agent prompts (opencode, or any compatible AI client) and the conductor will work — no shared/ directory required, no build step, no installer.

## What's in here

| File / Folder | Purpose |
|---|---|
| `conductor.md` | The orchestrator. Detects dispatch vs single-agent mode, plans, dispatches or self-plays. |
| `*.md` (12 more) | Specialist agents: builder, architect, reviewer, tester, docs, debugger, refactor, git, explorer, security, perf, planner. |
| `shared/` | Reusable prompt sections the conductor can cite. Kept for reference and easy editing. The 13 agent `.md` files do **not** depend on these. |
| `README.md` | This file. |

**Every `.md` file in the top level is fully self-contained** — all `{file:...}` references have been inlined. Copy any of them to a target project and it will run.

## Use in any project

```bash
# Copy one agent
cp conductor.md /path/to/other-project/.opencode/agents/

# Copy all 13 agents
cp *.md /path/to/other-project/.opencode/agents/

# Copy the whole folder (agents + shared reference)
cp -r . /path/to/other-project/.opencode/agents/
```

That's it. No `global-setup`, no `python setup.py`, no graphify required. Just copy.

## Operating modes

The conductor detects its environment on every session start:

| Mode | When | Behavior |
|---|---|---|
| **Dispatch mode** | env exposes a `task` / `delegate` / `@mention` tool | Conductor dispatches to real subagents in parallel; subagent boundaries are a hard contract |
| **Single-agent mode** | no dispatch tool detected | Conductor plays all roles (builder, reviewer, tester, etc.) sequentially using the subagent `.md` files as checklists; honest self-review |

The conductor announces its mode in the first response, so you always know what to expect.

## Editing an agent

Each agent `.md` is one self-contained file. Edit it directly. No `{file:...}` references to track. If you want to update shared content, you do it once per agent that uses it (the 13 agents each have their own copy of any shared sections they reference).

## Editing shared content

The `shared/` subfolder is for reference and easy editing. If you change a `shared/*.md` file, you'll need to manually re-inline the changes into any agent that includes it — the agents don't auto-update from `shared/`.

## Verifying

```bash
# Run the test suite to confirm all 13 agents are in working order
python -m pytest tests/test_install.py tests/test_operating_mode.py -v
```

The test `test_T_IN_2_global_setup_installs_resolved_agents` runs the full installer against a temp HOME and verifies the installed `conductor.md` has zero unresolved `{file:...}` references.

## Background

This folder is the result of three iterations:

- **Plan 001**: Replaced the old "MANDATORY: query the graph" soft constraint with a hard architectural split — conductor owns graphify queries, subagents consume.
- **Plan 002**: Added operating-mode detection so the agents work in any project (with or without a `task` tool). Shipped `dist/agents/` as a self-contained bundle.
- **Plan 003**: Promoted `dist/agents/` to be the source itself. This folder IS the deliverable. The redundant `dist/`, the build script, and the bundle tests are gone. One folder, one purpose, copy and paste.
