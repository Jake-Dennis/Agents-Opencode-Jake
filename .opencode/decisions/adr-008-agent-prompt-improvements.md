# ADR-008: Agent prompt improvements — shared sections, per-agent specialization, context protocol

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Jake Dennis (conductor session)

## Context and Problem Statement

An audit of the 13 agent prompts revealed 10 improvement opportunities:

1. **600+ lines of duplicated prompt sections** (Honesty, Consult, Use your tools, Graphify, Live progress tracking) were copy-pasted across all agents
2. **No per-agent tool preference guidance** — every agent had the same "Use your tools" section regardless of whether they could write or only read
3. **No graphify context in dispatch** — when the conductor dispatched a subagent, it sent a one-line @mention with no context
4. **No structured handoff format** — no standard for what a subagent passes back when done
5. **No agent boundaries** — every agent had the same "Consult before acting" section, but no explicit "you do NOT do X" boundaries
6. **No project context awareness** — each subagent started with zero memory of prior conversation
7. **No output format standards** — every agent produced freeform text with no predictable structure
8. **Planner had no self-validation** — plans could fail mechanical checks that verify-plan.py would catch
9. **No self-review step** — implementation agents could mark tasks done without re-reading their changes
10. **No conversation context protocol** — no `.opencode/context.md` for cross-session continuity

Additionally, the graphify MCP was confirmed to be correctly configured from https://github.com/safishamsi/graphify (PyPI package `graphifyy` v0.8.14, invoked via `python -m graphify.serve`).

## Decision Outcome

### Shared sections extracted to `.opencode/agents/shared/`

Created 8 reusable prompt section files:

| Section | File | Used by |
|---|---|---|
| Honesty | `shared/honesty.md` | All 13 agents |
| Consult before acting | `shared/consult.md` | All 13 agents |
| Use your tools | `shared/tools.md` | All 13 agents |
| Graphify | `shared/graphify.md` | All 13 agents |
| Live progress tracking | `shared/progress-tracking.md` | 8 write-capable agents |
| Live progress tracking (read-only) | `shared/progress-tracking-readonly.md` | 7 read-only agents |
| Handoff format | `shared/handoff.md` | 6 implementation agents |
| Self-review | `shared/self-review.md` | 6 implementation agents |
| Project context | `shared/project-context.md` | All 13 agents |

Each agent prompt now includes these via `{file:./.opencode/agents/shared/X.md}` references. The total prompt text per agent dropped from ~4,500 chars of duplicated content to ~1,500 chars of unique role + 8 `{file:}` references.

### Per-agent specialization added

Each agent now has:
- **Tool preferences** — explicitly lists which tools to prefer and which to avoid
- **Boundaries** — explicitly lists what the agent does NOT do
- **Output format** — a structured template for consistent output

### Conductor dispatch context rule

Added a `## Dispatching with context` section to the conductor: "When you dispatch a subagent, ALWAYS include relevant graph context inline."

### New: `.opencode/context.md`

A template file that the conductor maintains. Each subagent reads it before starting. Contains: what happened, key decisions, files modified, what the next agent needs to know.

### Planner self-validation

Added a `## Self-validation` section to the planner that lists the 5 mechanical checks from verify-plan.py (layer format, @-assignment, description length, verification coverage, no duplicate IDs).

### Graphify MCP confirmed correct

The MCP config `"graphify": {"type": "local", "command": ["python", "-m", "graphify.serve", "graphify-out/graph.json"]}` correctly uses the `safishamsi/graphify` package (PyPI: `graphifyy` v0.8.14). No changes needed.

## Consequences

### Positive

- **Eliminated 600+ lines of prompt duplication** — changes to shared sections now update all agents at once
- **Each agent has clear boundaries** — reduces risk of agents doing each other's jobs
- **Standardized output** — each agent produces predictably-structured output
- **Context flows between agents** — `.opencode/context.md` gives continuity across dispatches
- **Planner catches structural errors before verify-plan.py** — self-validation rules mirror the mechanical checks

### Negative

- **8 new files to maintain** — the shared sections are separate files that must be kept in sync with agent requirements
- **`{file:}` resolution in tests** — tests that check prompt content must now recursively resolve `{file:}` references (the `_resolve_prompt()` helper handles this)
- **Context.md can become stale** — requires conductor discipline to keep updated; if the conductor forgets, subagents may work with outdated context