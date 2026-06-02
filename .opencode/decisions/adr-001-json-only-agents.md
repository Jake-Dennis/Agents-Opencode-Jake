# ADR-001: JSON-only agent architecture

- **Status:** Accepted
- **Date:** 2026-06-03
- **Deciders:** Jake Dennis (conductor session)

## Context and Problem Statement

The project started with agents defined in two places:
1. `opencode.json` (registry of all 13 agents)
2. `.opencode/agents/*.md` (per-agent files with YAML frontmatter)

This dual-source approach was inspired by oh-my-openagent. We discovered two blocking problems:

**Problem A — Mode override bug.** When `.opencode/agents/conductor.md` had `mode: subagent` in frontmatter but `opencode.json` had `mode: primary`, the merged config used `subagent` (from MD). This silently demoted the conductor and broke Tab-switching.

**Problem B — Command schema mismatch.** The `command` field in `opencode.json` requires `template:` (per the opencode schema), not `prompt:`. We discovered this only when `opencode agent list` rejected the config with a schema error. Test scripts caught it eventually but it blocked initial setup for hours.

How should we structure agent definitions to avoid these issues?

## Considered Options

1. **JSON-only (consolidate everything to opencode.json)** — single source of truth, no merging
2. **Keep .md files, add JSON validator** — preserve familiar authoring, prevent bugs at edit time
3. **Use opencode.jsonc with comments** — JSON5-style, allows inline docs

## Decision Outcome

**Chosen option: 1 — JSON-only.** Consolidate all 13 agent definitions to `opencode.json` with `prompt` fields inline. Delete all `.opencode/agents/*.md` files. The 11 subagents are promoted from `mode: subagent` to `mode: all` so they remain both CLI-testable (`opencode run --agent <name>`) and @mention-dispatchable.

### Consequences

**Good:**
- Single source of truth — no merge conflicts, no override bugs
- Schema validation works (we now have `opencode.schema.json`)
- All 4 test suites can read one file
- 13 → 0 .md files, simpler mental model

**Bad:**
- Prompts are now inline strings in JSON — hard to author large prompts without a JSON-aware editor
- Lost the ability to write prompts in pure Markdown (no frontmatter, no syntax highlighting)
- `opencode.json` is 26 KB — large for hand-editing

**Mitigations:**
- Plan #1 task #3 (this plan) creates a JSON schema for validation
- Plan #1 task #5 (this plan) creates an E2E test that catches config breaks
- Plan #1 task #13 (this plan) adds a pre-commit hook with basic JSON validation

### Confirmation

The decision was confirmed by:
- All 4 test suites passing (645/645 checks)
- All 13 agents responding correctly via `opencode run --agent <name>`
- Discovery that the conductor's prompt fits cleanly in inline JSON (no need for a separate .md)

## Pros and Cons of the Options

### Option 1: JSON-only

- **Good:** No merge conflicts, schema-validatable, single file
- **Bad:** Less ergonomic for authoring large prompts, 26 KB is large
- **Bad:** Loses the "agent as a markdown file" pattern that mirrors how opencode docs describe agents

### Option 2: Keep .md + JSON validator

- **Good:** Familiar authoring, prompts in pure Markdown
- **Good:** JSON validator catches the `template:` vs `prompt:` bug
- **Bad:** Still has the merge conflict risk — what wins if JSON and .md disagree?
- **Bad:** Two sources of truth means two places to update when adding an agent

### Option 3: opencode.jsonc with comments

- **Good:** JSON5-style allows `//` comments and unquoted keys
- **Good:** Single file, single source of truth
- **Bad:** opencode CLI may not parse .jsonc — would need to convert at build time
- **Bad:** Loses the ability to JSON.parse() the file in scripts (need a JSON5 parser)

## References

- Commit: `d4fbfe0 Initial release: 13-agent collection with conductor + graphify` (consolidation already in this commit)
- `opencode.json` (the consolidated config)
- `tests/test_schema.py` (validates the config)
- Plan 001 task #3 (the JSON schema)
