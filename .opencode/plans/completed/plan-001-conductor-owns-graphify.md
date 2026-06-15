# Plan 001: Conductor owns graphify; subagents consume

## Goal

Make graphify usage **structural** rather than aspirational. The conductor becomes the **sole owner** of knowledge-graph queries; subagents **consume** the `Graph context:` block the conductor hands them and never query the graph themselves. Currently the prompt language says "you MUST" and "MANDATORY" but LLMs skip it because they're overloaded with similar soft-constraint language. The fix is to make the wrong path impossible: the conductor's dispatch template requires the block, and the subagent prompt says "stop if missing" — a missing block becomes a visible dispatch failure rather than a silent omission.

## Tasks

### Layer 1 — Protocol rewrite (parallel, no deps)
- [ ] #1 - Rewrite `.opencode/agents/shared/graphify.md` to remove the "no context → query yourself" branch and reframe as "conductor-owned, subagent-consumed" (assigned: @conductor)
- [ ] #2 - Update `.opencode/agents/conductor.md`: new line 1 framing + expand Step 5 to require graph queries before every dispatch (assigned: @conductor)
- [ ] #3 - Update `AGENTS.md` dispatch template: tighten "primary mechanism" → "sole mechanism" and add explicit failure-mode language (assigned: @conductor)
- [ ] #4 - Replace line 1 in all 12 subagent `.md` files (builder, architect, reviewer, tester, docs, debugger, refactor, git, explorer, security, perf, planner) with the consume-only framing (assigned: @conductor)

## Verification
- [ ] #1 - `grep -r "MANDATORY" .opencode/agents/*.md` returns 0 results in the line-1 of any agent file (old wording fully removed)
- [ ] #2 - `grep -r "query the graph yourself" .opencode/agents/` returns 0 results
- [ ] #3 - `grep -l "Graph context:" .opencode/agents/conductor.md AGENTS.md` confirms both files reference the block in their dispatch protocol
- [ ] #4 - All 13 agent .md files have a line 1 that begins with `> Your dispatch from the conductor` (or `> You own the knowledge graph` for conductor.md itself)
- [ ] #5 - Re-read each of the 15 modified files and confirm semantic correctness (line 1 reflects consume-only model, shared/graphify.md has no self-query branch, conductor.md Step 5 mandates graph queries before dispatch)
- [ ] #6 - `.opencode/work-log.md` has a new entry for this plan; `.opencode/context.md` reflects current session state
