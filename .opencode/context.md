# Project Context

> Auto-maintained by the conductor. Each subagent reads this before starting their task.
> Updated at the start and end of each work cycle.

## Current session

- **Date:** 2026-06-15
- **Active plans:** plan-001 + plan-002 both complete, awaiting commit
- **Files modified this session:**
  - `.opencode/plugins/graphify.js` (added by `graphify install --platform opencode`)
  - `.opencode/opencode.json` (added — registers the graphify plugin)
  - `.opencode/package.json` (added — declares `@opencode-ai/plugin` v1.15.13)
  - `.opencode/agents/shared/graphify.md` (rewritten — removed self-query branch)
  - `.opencode/agents/conductor.md` (line 1 + Step 5 + new "Operating mode" section)
  - `AGENTS.md` (Dispatch Template section tightened to "sole mechanism")
  - `.opencode/agents/{builder,architect,reviewer,tester,docs,debugger,refactor,git,explorer,security,perf,planner}.md` (line 1 replaced + self-mode note added × 12)
  - `tests/test_graphify_protocol.py` (new — 28 regression tests for plan-001)
  - `tests/test_operating_mode.py` (new — 18 regression tests for plan-002)
  - `tests/test_bundle.py` (new — 5 regression tests for plan-002 bundle)
  - `scripts/build-self-contained-bundle.py` (new — produces `dist/agents/*.md`)
  - `dist/agents/{13 agents + MANIFEST.md}` (new — self-contained bundle, tracked in git)
  - `INSTALL.md` (new "Use the Agents in Any Project" section)
  - `.opencode/plans/{plan-001,plan-002}*.md` (new)
  - `.opencode/context.md` (this file)
  - `.opencode/work-log.md` (appended)
  - `.opencode/todo.md` (plan-001 + plan-002 added)

## Key decisions

- **No-op install**: graphify was already partially wired — Python package v0.8.14 installed, skill at `~/.config/opencode/skills/graphify/`, MCP server config in root `opencode.json`. Ran `graphify install --platform opencode` to clear the version-drift warning, add the project-level plugin hook, and register the plugin.
- **Conductor owns graphify, subagents consume** (plan 001): The previous "MANDATORY: query yourself" language was a soft constraint LLMs were skipping. Refactored to a hard architectural split: conductor is the **sole** owner of graphify queries, subagents **consume** the `Graph context:` block from the dispatch and never query themselves. A missing block is now a visible dispatch failure (subagent stops and reports it), not a silent omission.
- **Operating mode + self-contained bundle** (plan 002): The user reported the agents don't work in projects without a `task` tool. Root cause: conductor prompt assumed dispatch mode. Fix is two-part — (1) conductor detects its environment at session start and announces dispatch or single-agent mode, with honest self-review limits documented for single-agent; (2) ship a `dist/agents/*.md` self-contained bundle so any project can copy a single file and have a working agent. Tracked `dist/` in git (it's a primary deliverable, not a build artifact).
- **Plan 002 retracts an earlier proposed fix.** I initially proposed adding a "no direct implementation" hard rule to conductor.md. The user shared the actual agent response from another project, which self-corrected and identified the missing dispatch tool as the real issue. The right fix is operating-mode detection (works anywhere), not refusal (works nowhere).

## Verification

- `graphify --help` runs clean, no version warning
- `python -m graphify.serve graphify-out/graph.json` boots as stdio MCP server, stays alive
- plan-001 verification: `MANDATORY.*query the graph yourself` returns 0 matches; all 12 subagent line-1s + conductor line-1 + shared/graphify.md rewrite confirmed correct
- plan-002 verification: 18/18 operating-mode tests pass, 5/5 bundle tests pass, full suite 245/1-pre-existing-fail/1-skip (was 222 before plan-002, +23 new tests, no regressions)
- `dist/agents/conductor.md` is 21,158 bytes (vs source ~10,200) — includes inlined correctly

## What the next agent needs to know

- The graphify protocol is now: I (conductor) always run `graphify_graph_stats` + `graphify_query_graph` before dispatch, format into a `Graph context:` block, and inline it at the top of every dispatch. Subagents never query the graph themselves.
- The operating-mode protocol is: at session start, check available tools. If `task` / `delegate` / `@mention` runtime present → dispatch mode. Otherwise → single-agent mode. **State the mode in the first response** so the user knows.
- In single-agent mode, the conductor plays all roles sequentially: Conductor → Builder → Tester → Reviewer (self) → Documenter. Use the subagent `.md` files as checklists. Self-review is honest self-review with acknowledged limits.
- The plugin hook (`.opencode/plugins/graphify.js`) injects a one-shot bash reminder per session — belt-and-suspenders for direct shell users, not the primary mechanism.
- The self-contained bundle at `dist/agents/*.md` is tracked in git. To use the agents in another project, copy the relevant `.md` files to the target project's agent directory. No build step, no graphify, no skill symlinks required.
- A "missing Graph context" report from any subagent means I forgot, not that the subagent is being stubborn. Fix the dispatch.
- graphify CLI is at `C:\Users\JakeP\AppData\Local\Programs\Python\Python311\Scripts\graphify.exe` (user-level, on PATH).
- Run `/graphify .` to rebuild the knowledge graph; `/graphify . --update` to incrementally refresh.
- Run `graphify install --platform opencode` any time the package version drifts ahead of the installed skill.
- Run `python scripts/build-self-contained-bundle.py` to rebuild the bundle. CI/test pipeline should run this.