# Project Context

> Auto-maintained by the conductor. Each subagent reads this before starting their task.
> Updated at the start and end of each work cycle.

## Current session

- **Date:** 2026-06-15
- **Active plan:** plan-001-conductor-owns-graphify.md (complete, awaiting commit)
- **Files modified this session:**
  - `.opencode/plugins/graphify.js` (added by `graphify install --platform opencode`)
  - `.opencode/opencode.json` (added — registers the graphify plugin)
  - `.opencode/package.json` (added — declares `@opencode-ai/plugin` v1.15.13)
  - `.opencode/agents/shared/graphify.md` (rewritten — removed self-query branch)
  - `.opencode/agents/conductor.md` (line 1 + Step 5 expanded)
  - `AGENTS.md` (Dispatch Template section tightened to "sole mechanism")
  - `.opencode/agents/{builder,architect,reviewer,tester,docs,debugger,refactor,git,explorer,security,perf,planner}.md` (line 1 replaced × 12)
  - `.opencode/plans/plan-001-conductor-owns-graphify.md` (new)
  - `.opencode/context.md` (this file)
  - `.opencode/work-log.md` (appended)

## Key decisions

- **No-op install**: graphify was already partially wired — Python package v0.8.14 installed, skill at `~/.config/opencode/skills/graphify/`, MCP server config in root `opencode.json`. Ran `graphify install --platform opencode` to clear the version-drift warning, add the project-level plugin hook, and register the plugin.
- **Conductor owns graphify, subagents consume** (plan 001): The previous "MANDATORY: query yourself" language was a soft constraint LLMs were skipping. Refactored to a hard architectural split: conductor is the **sole** owner of graphify queries, subagents **consume** the `Graph context:` block from the dispatch and never query themselves. A missing block is now a visible dispatch failure (subagent stops and reports it), not a silent omission.

## Verification

- `graphify --help` runs clean, no version warning
- `python -m graphify.serve graphify-out/graph.json` boots as stdio MCP server, stays alive
- `graph.json` is 1.8 MB, 2195 nodes / 173 communities
- plan-001 verification: `MANDATORY.*query the graph yourself` returns 0 matches; all 12 subagent line-1s + conductor line-1 + shared/graphify.md rewrite confirmed correct

## What the next agent needs to know

- The graphify protocol is now: I (conductor) always run `graphify_graph_stats` + `graphify_query_graph` before dispatch, format into a `Graph context:` block, and inline it at the top of every dispatch. Subagents never query the graph themselves.
- The new project-level plugin hook (`.opencode/plugins/graphify.js`) still injects a one-shot bash reminder per session, but it's belt-and-suspenders — the primary mechanism is the dispatch block.
- A "missing Graph context" report from any subagent means I forgot, not that the subagent is being stubborn. Fix the dispatch.
- graphify CLI is at `C:\Users\JakeP\AppData\Local\Programs\Python\Python311\Scripts\graphify.exe` (user-level, on PATH).
- Run `/graphify .` to rebuild the knowledge graph; `/graphify . --update` to incrementally refresh.
- Run `graphify install --platform opencode` any time the package version drifts ahead of the installed skill.