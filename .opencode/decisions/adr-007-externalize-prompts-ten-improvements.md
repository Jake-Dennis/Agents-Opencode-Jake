# ADR-007: Externalize agent prompts and ten structural improvements

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Jake Dennis (conductor session)

## Context and Problem Statement

An audit of the project identified 10 structural improvements ranging from maintainability bugs to CI gaps:

1. **71KB of duplicated prompt text** — 4 shared sections (Honesty, Consult, Use your tools, Live progress tracking) copy-pasted across 13 agents in opencode.json
2. **No top-level model key** — the documented two-tier model strategy didn't work; every agent used its `fallback_model` as the primary with no fallback
3. **AGENT-ROLES.md ↔ opencode.json could silently drift** — only human review kept them in sync
4. **Hard-coded absolute path** in test_agents_runtime.py — only worked on one machine
5. **Knowledge graph check was a hard gate** — new projects couldn't verify any plan before running `/graphify`
6. **Inline prompts in opencode.json** — only the conductor had an externalized prompt; the other 12 were 4-6KB strings in JSON
7. **CI didn't run full suite on Windows** — test.yml only ran 4 of 19 tests
8. **Two overlapping CI workflows** — ci.yml and test.yml triggered on same events with overlapping checks
9. **No /status command** — no way to quickly check project state
10. **jobs.md format was prose-only** — no machine-parseable field spec

## Decision Outcome

### #1/#6: Externalize all 13 agent prompts to .md files

All 13 agents now use `{file:./.opencode/agents/<name>.md}` as their prompt. The `opencode.json` file went from 71,259 chars to 9,879 chars (86% reduction). Shared sections (honesty, consult, tools, progress tracking) remain inline in each `.md` file — a future improvement may extract them into includes. The `{file:}` directive is validated by `opencode.schema.json` (pattern `^\{file:\.\.\/.*\.md\}$`).

### #2: Add top-level model key

Added `"model": "opencode/nemotron-3-ultra-free"` to `opencode.json`. Fixed all fallback models to differ from the primary (all now use `opencode/deepseek-v4-flash-free`). Updated `test_all_agents_inherit_top_level_model` to also verify fallback models differ from the primary.

### #3: Agent-registry sync check (7th mechanical check)

Added check #7 to `verify-plan.py`: parses `opencode.json` agent names and `AGENT-ROLES.md` table rows, fails if any agent appears in one but not the other. This is a hard gate (blocks plan verification on mismatch). Two new tests (`test_T_MC_7`, `test_T_MC_8`) verify pass and fail cases.

### #4: Fix hard-coded path

Changed `PROJECT = Path(r"C:\Users\JakeP\...")` to `PROJECT = Path(__file__).resolve().parent.parent` in test_agents_runtime.py.

### #5: Make graph check advisory

The knowledge-graph-exists check (#6) no longer blocks plan verification. It prints a warning but allows plans to proceed. Only hard mechanical failures block verification.

### #7/#8: Merge CI into matrix workflow

Merged ci.yml (Ubuntu) and test.yml (Windows) into a single ci.yml with `matrix.os: [ubuntu-latest, windows-latest]`. Both platforms now run the full test suite. Deleted test.yml.

### #9: /status command

Created `.opencode/commands/status.md` with frontmatter description and instructions for the conductor to report active plans, tests, knowledge graph health, and blocked items.

### #10: jobs.md machine-parseable spec

Added a "Machine-parseable fields" section to `.opencode/jobs.md` documenting the exact schema for `Status`, `Started`, `Last update`, `Current step`, `Sub-steps`, `Notes`, and the header parsing rules (`<plan-id>`, `<agent>`, `<task summary>`).

## Consequences

### Positive

- **opencode.json is now scannable** — 9.9KB vs 71KB, each agent entry is ~15 lines
- **Model strategy works as documented** — top-level `model` makes fallback_model actually a fallback
- **Drift is caught mechanically** — verify-plan.py will block plans if AGENT-ROLES.md and opencode.json disagree
- **CI covers both platforms** — Windows tests are no longer a subset
- **New projects can verify plans** — missing graph is a warning, not a blocker

### Negative

- **13 .md files to maintain** — shared sections are still duplicated across files (honesty, consult, tools, progress tracking). A future improvement should extract these into composable includes
- **{file:} resolution in tests** — tests that check prompt content must resolve `{file:}` references before searching. The `_resolve_prompt()` helper in test_jobs.py handles this
- **Pre-existing test failures remain** — T_AS_1 (steps field) and T_AS_5 (conductor steps) test for a `steps` key that was never in opencode.json. These are out of scope for this plan

## Verification

Run `python scripts/verify-plan.py .opencode/plans/plan-016-ten-improvements.md` and `python -m pytest tests/ -v --tb=short`. Out of scope: the two pre-existing test_agent_safety failures (T_AS_1, T_AS_5) which test for a `steps` field that doesn't exist in the current config.