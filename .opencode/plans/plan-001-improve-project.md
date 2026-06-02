# Plan 001: Comprehensive Project Improvements

## Goal
Address all 15 improvement opportunities identified through graph analysis, test audit, and project review. Organize into dependency layers so independent work runs in parallel. End state: tests are versioned, the project has CI/CD, the knowledge graph is deeper, and the JSON-only agent architecture is documented and constrained.

## Architectural Context
- Repo: `C:\Users\JakeP\Documents\GitHub\Agents-Opencode-Jake`
- Current state: 645/645 tests pass, 1 commit on `main`, knowledge graph has 161 nodes / 187 edges / 17 communities
- Graph has surfaced these concrete gaps: 14 `model` keys with no value constraint edges, 11 tiny schema-sibling communities, 4 unverified INFERRED edges on Conductor Agent
- All 15 improvements were identified from running the project + tracing the graph

## Tasks

### Layer 1 (parallel, no dependencies — 6 tasks)

- [x] **#1 — Move tests into the repo** (assigned: @builder) — DONE 2026-06-03
  - Created `tests/` with 4 moved files + `__init__.py` + `conftest.py` (basic fixtures) + `pytest.ini`
  - Updated `.gitignore` for `__pycache__/`
  - 632/632 script-style checks still pass when run as scripts

- [x] **#2 — Re-run `/graphify . --update`** (assigned: conductor [direct]) — DONE 2026-06-03
  - Subsumed by #6 (full --deep run) which captured all 8 new files
  - Graph grew from 161 → 275 nodes, 187 → 314 edges

- [x] **#3 — JSON schema for `opencode.json`** (assigned: @architect) — DONE 2026-06-03
  - `opencode.schema.json` (1,973 bytes, Draft 2020-12) at repo root
  - `tests/test_schema.py` with 4 pytest tests — all pass
  - Regression test for `template` vs `prompt` in commands is in place

- [x] **#4 — First ADR: JSON-only agent architecture** (assigned: @docs) — DONE 2026-06-03
  - `.opencode/decisions/adr-001-json-only-agents.md` (83 lines, MADR template)
  - Captures Problem A (mode override), Problem B (template bug), and the decision rationale

- [x] **#6 — Run `/graphify . --deep`** (assigned: conductor [direct]) — DONE 2026-06-03
  - Full re-extraction with deep INFERRED edges
  - 12 new nodes for schema/ADR/plan/test files, 6 INFERRED edges (e.g. `template_schema_mismatch → template_field`)

- [x] **#11 — Add LICENSE file** (assigned: @docs) — DONE 2026-06-03
  - `LICENSE` (1,068 bytes, MIT, Copyright 2026 Jake Dennis)
  - `README.md` License section now references it

### Layer 2 (depends on Layer 1 — 7 tasks)

- [ ] **#5 — End-to-end conductor workflow test** (assigned: @tester, depends on #1, #3)
  - File: `tests/test_conductor_workflow.py`
  - Test: write a fake plan to `.opencode/plans/test-plan.md`, invoke conductor with that plan as input, verify the plan gets executed (or a child plan is created), work-log gets appended, todo gets updated
  - This is the missing test — it validates the actual user-facing workflow, not just individual agents
  - Uses `OPENCODE_SERVER_PASSWORD` unset workaround

- [ ] **#7 — GitHub Actions CI** (assigned: @builder, depends on #1)
  - File: `.github/workflows/test.yml`
  - Triggers: push to `main`, all pull requests
  - Runs on: `windows-latest`
  - Steps: checkout → setup Python 3.11 → `pip install pytest networkx` → `pytest tests/`
  - **Why:** prevents regressions; runs the 4 test suites on every PR

- [ ] **#9 — `tests/conftest.py` with shared fixtures** (assigned: @tester, depends on #1)
  - Already part of #1, but expand here: add `agent_cfg(name)` fixture, `runtime_timeout` fixture, `graph_data` fixture
  - Use these fixtures in the existing 4 test files to remove duplication
  - Target: ~3x faster test runs

- [ ] **#8 — Generate Obsidian vault** (assigned: conductor [direct], depends on #2 OR #6)
  - Run `/graphify . --obsidian`
  - Outputs: 161 .md notes + 17 `_COMMUNITY_*` notes + `graph.canvas` in `graphify-out/obsidian/`
  - Note: vault is gitignored (graphify-out/), but the user can copy it elsewhere
  - Visual way to explore the agent ecosystem

- [ ] **#10 — Generate wiki** (assigned: conductor [direct], depends on #2 OR #6)
  - Run `/graphify . --wiki`
  - Outputs: `graphify-out/wiki/index.md` + per-community articles
  - Human-readable Markdown alternative to Obsidian
  - Good for sharing with collaborators

- [ ] **#12 — `examples/` directory** (assigned: @docs, depends on #4)
  - File: `examples/add-an-agent.md` — walkthrough for adding a 14th custom agent
  - File: `examples/use-conductor.md` — walkthrough of running the conductor on a real task
  - File: `examples/integrate-into-your-project.md` — quick start for using this collection
  - **Why after #4:** examples reference the ADR's "JSON-only" decision

- [ ] **#13 — Pre-commit hook** (assigned: @builder, depends on #1)
  - File: `.git/hooks/pre-commit` (or `scripts/install-hook.sh` + `scripts/pre-commit`)
  - Runs `test_setup.py` and `test_integration.py` (the static tests, skip the slow runtime one)
  - Blocks commit if tests fail
  - Optional: also run `python -c "import json; json.load(open('opencode.json'))"` for basic JSON validation

### Layer 3 (depends on Layer 2 — 2 tasks)

- [ ] **#14 — Schema-instance pattern in graph** (assigned: @architect + @builder, depends on #3, #6)
  - Design: create an `AgentConfigSchema` template node (6 keys: description, mode, model, fallback_model, permission, prompt)
  - Add 13 `instance_of` edges from each agent → `AgentConfigSchema`
  - Add 13 `has_field` edges from `AgentConfigSchema` → each of the 6 key nodes
  - Implementation: re-run `/graphify . --update` with the schema in place
  - Trade-off: collapses 11 "agent-config" communities → 1; loses per-agent discoverability but gains semantic clarity
  - Verify: `graph.html` shows collapsed communities; `GRAPH_REPORT.md` reflects the new structure

- [ ] **#15 — Model value constraints in graph** (assigned: @architect, depends on #3, #6)
  - Design: add value nodes (`value_minimax_m3_free`, `value_big_pickle`, `value_opencode`)
  - Add `has_value` edges from each `model`/`fallback_model` key node → the value node
  - Add `same_value_as` edges between all 14 model nodes (or rather, the value node is the single source of truth)
  - Implementation: extend the JSON schema (#3) to validate model values are from an enum; re-run `/graphify . --update` with value-aware extraction
  - Verify: graph can answer "which agents use big-pickle as fallback?" in one BFS hop

## Verification

For each task, the verification step:

- [ ] #1 — `pytest tests/ --collect-only` shows all 4 test files; `git status` shows no `tests/` files untracked after move
- [ ] #2 — `graphify-out/graph.json` has more nodes than before (≥162), `GRAPH_REPORT.md` lists README.md in the corpus
- [ ] #3 — `python -c "import jsonschema, json; jsonschema.validate(json.load(open('opencode.json')), json.load(open('opencode.schema.json')))"` exits 0
- [ ] #4 — `.opencode/decisions/adr-001-json-only-agents.md` exists; follows the ADR template (Context, Decision, Consequences, Alternatives)
- [ ] #5 — `pytest tests/test_conductor_workflow.py` passes; the test creates a plan, runs conductor, and verifies `.opencode/plans/completed/` gets a new file
- [ ] #6 — `graphify-out/GRAPH_REPORT.md` shows >6 INFERRED edges (was 6); community count same or higher
- [ ] #7 — `.github/workflows/test.yml` exists; pushing to a test branch triggers the workflow
- [ ] #8 — `graphify-out/obsidian/` exists with `index.md`, `_COMMUNITY_*.md`, and `graph.canvas`
- [ ] #9 — `tests/conftest.py` exports `cfg`, `repo` fixtures; existing tests use them
- [ ] #10 — `graphify-out/wiki/index.md` exists and links to per-community articles
- [ ] #11 — `LICENSE` exists with MIT text; `README.md` references it
- [ ] #12 — `examples/` has 3 files, each ≥30 lines, each demonstrating one workflow
- [ ] #13 — `.git/hooks/pre-commit` runs and blocks a commit with a broken test
- [ ] #14 — `graph.html` shows `AgentConfigSchema` as a hub node; community count drops from 17 → 7
- [ ] #15 — `graph.html` shows `value_minimax_m3_free` connected to all 14 model keys; querying "fallback big-pickle" returns all 13 agents in one hop

## Final State (after all 15 done)

- **Tests:** 4 → 6+ suites, ~700 checks, all in version control, running in CI on every PR
- **Graph:** 161 nodes → ~250 nodes, 187 edges → ~400 edges, 17 communities → 7 communities (collapsed via schema-instance), value constraints expressed
- **Documentation:** LICENSE, README, ADRs, examples, all consistent
- **CI/CD:** GitHub Actions + pre-commit hook, tests run on every commit and PR
- **Architecture:** JSON-only agents documented as an ADR; JSON schema enforces it; future changes constrained
- **Total commit history:** 1 → ~10+ commits, well-structured

## Estimated Effort

| Task | Effort | Skill |
|---|---|---|
| #1  Move tests | 30 min | builder |
| #2  graphify --update | 2 min | conductor |
| #3  JSON schema | 2 hr | architect |
| #4  First ADR | 15 min | docs |
| #5  E2E conductor test | 3-4 hr | tester |
| #6  graphify --deep | 10 min | conductor |
| #7  CI workflow | 30 min | builder |
| #8  Obsidian vault | 2 min | conductor |
| #9  conftest.py | 1 hr | tester |
| #10 Wiki | 2 min | conductor |
| #11 LICENSE | 5 min | docs |
| #12 examples/ | 2 hr | docs |
| #13 pre-commit hook | 30 min | builder |
| #14 schema-instance | 2-3 hr | architect + builder |
| #15 value constraints | 2-3 hr | architect |
| **Total** | **~16-20 hr** | mixed |

## How to execute

The `/build` command reads this file and dispatches all tasks in dependency order:

1. Dispatches Layer 1 in parallel (4 subagents max per message)
2. Waits for all Layer 1 to complete
3. Dispatches Layer 2 in parallel
4. Waits, dispatches Layer 3
5. After all tasks complete, runs the full test suite + final summary

Run with: `/build`
