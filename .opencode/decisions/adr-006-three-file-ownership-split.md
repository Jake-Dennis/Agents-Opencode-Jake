# ADR 006: Three-File Ownership Split (todo.md / work-log.md / jobs.md)

- **Date:** 2026-06-08
- **Status:** Accepted
- **Deciders:** conductor, @architect
- **Supersedes:** Decentralized logging (pre-plan-013, everyone wrote to work-log.md)

## Context

Before plan-013, the project had two tracking artifacts:

- `.opencode/todo.md` — a high-level plan checklist managed by the conductor
- `.opencode/work-log.md` — an append-only running log of all work cycles

Neither worked well for live progress tracking during multi-agent dispatches. The conductor updating `todo.md` gave plan-level visibility (Layer 1, Layer 2) but no sub-step granularity. The subagents had no place to report "I'm working on task X, currently at sub-step Y" without cluttering the work-log or the todo.

A separate artifact was needed — one that subagents could write to at will without disrupting the conductor's plan-level tracking or the historical work-log.

## Decision

Establish a **three-file ownership split** with strict boundaries:

| Artifact | Owner(s) | Purpose | Update pattern |
|---|---|---|---|
| `.opencode/todo.md` | Conductor (only) | High-level plan checklist, one row per Layer 1/2 task | Conductor's steps 4-6 (TODO, DISPATCH, TRACK) |
| `.opencode/work-log.md` | Conductor (only) | Append-only historical record of completed work cycles | Conductor steps 9-10 (DOCUMENT, SYNC TODO) |
| `.opencode/jobs.md` | 11 write-capable subagents | Fine-grained live status, one entry per dispatch | Subagents update in real-time via 3 rules (Start/As you work/Finish) |

### The 3 update rules for jobs.md

1. **Start**: Append a new entry `## [<plan-id>] @<agent> - <task>` with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: Update `Last update` and `Current step`; flip sub-steps `[ ]` → `[~]` → `[x]`.
3. **Finish**: Set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

### Agent-to-artifact permissions

| Agent | todo.md | work-log.md | jobs.md |
|---|---|---|---|
| Conductor | ✅ write | ✅ write | ❌ (does not write) |
| 6 impl agents (builder, tester, docs, debugger, refactor, perf) | ❌ | ❌ | ✅ write |
| 5 readonly agents (planner, architect, reviewer, explorer, security) | ❌ | ❌ | ✅ write (scoped `edit: {jobs.md: allow, *: deny}`) |
| git agent | ❌ | ❌ | ❌ (stays on bash only) |

## Consequences

**Positive:**
- Clear ownership eliminates confusion about "who should update what"
- Subagents have a dedicated space for live progress without cluttering conductor artifacts
- The 3 update rules are simple enough to be included verbatim in each subagent's prompt (~600 chars)
- Testable: T-JB-1..T-JB-6 verify all boundaries

**Negative:**
- `jobs.md` grows unbounded over time (mitigation: plan-014 #13 adds archival/rotation to conductor's step 10)
- New subagents must be explicitly added to the permission model (currently hardcoded in opencode.json)
- The conductor does NOT see subagent updates in real-time — it must read `jobs.md` between dispatch layers (mitigation: see the plan-013 design)

**Neutral:**
- `todo.md` and `work-log.md` remain append-only for the conductor; no retroactive edits
- Can be extended to more agents or more artifacts without changing the ownership model
