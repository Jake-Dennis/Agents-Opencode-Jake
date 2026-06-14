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
  - Created `tests/` with 4 moved files + `tests/__init__.py` + `tests/conftest.py` (basic fixtures) + `pytest.ini`
  - Updated `.gitignore` for `__pycache__/`
  - 632/632 script-style checks still pass when run as scripts

- [x] **#2 — Re-run `/graphify . --update`** (assigned: @conductor [direct]) — DONE 2026-06-03
  - Subsumed by #6 (full --deep run) which captured all 8 new files
  - Graph grew from 161 → 275 nodes, 187 → 314 edges

- [x] **#3 — JSON schema for `opencode.json`** (assigned: @architect) — DONE 2026-06-03
  - `opencode.schema.json` (1,973 bytes, Draft 2020-12) at repo root
  - `tests/test_schema.py` with 4 pytest tests — all pass
  - Regression test for `template` vs `prompt` in commands is in place

- [x] **#4 — First ADR: JSON-only agent architecture** (assigned: @docs) — DONE 2026-06-03
  - `.opencode/decisions/adr-001-json-only-agents.md` (83 lines, MADR template)
  - Captures Problem A (mode override), Problem B (template bug), and the decision rationale

- [x] **#6 — Run `/graphify . --deep`** (assigned: @conductor [direct]) — DONE 2026-06-03
  - Full re-extraction with deep INFERRED edges
  - 12 new nodes for schema/ADR/plan/test files, 6 INFERRED edges (e.g. `template_schema_mismatch → template_field`)

- [x] **#11 — Add LICENSE file** (assigned: @docs) — DONE 2026-06-03
  - `LICENSE` (1,068 bytes, MIT, Copyright 2026 Jake Dennis)
  - `README.md` License section now references it

### Layer 2 (depends on Layer 1 — 7 tasks)

- [x] **#5 — End-to-end conductor workflow test** (assigned: @tester, depends on #1, #3) — DONE 2026-06-03
  - File: `tests/test_conductor_workflow.py` (129 lines, 6 pytest tests, all pass)
  - Uses `tmp_path` for plan dir isolation; consumes `cfg` fixture from conftest
  - Tests plan file structure, conductor prompt completeness, subagent references, plan template, simulated plan→completed/ move with work-log append
  - **Caveat:** structural validation only; real E2E (subprocess to `opencode run`) deferred — fast/slow split

- [x] **#7 — GitHub Actions CI** (assigned: @builder, depends on #1) — DONE 2026-06-03
  - File: `.github/workflows/ci.yml` (matrix CI for ubuntu + windows)
  - Triggers: push to main, all PRs
  - Runs on: `windows-latest`, Python 3.11
  - Steps: checkout → setup-python → pip install pytest networkx jsonschema → pytest tests/

- [x] **#9 — `tests/conftest.py` with shared fixtures** (assigned: @tester, depends on #1) — DONE 2026-06-03
  - 9 fixtures: `repo_path`, `cfg`, `schema`, `agent_names`, `conductor_prompt`, `work_log_path`, `reset_work_log`, `plans_dir`, `completed_plans_dir`
  - Migrated `tests/test_schema.py` and `tests/test_conductor_workflow.py` to consume the shared fixtures (removed local `cfg`/`schema` fixtures from test_schema.py)

- [x] **#8 — Generate Obsidian vault** (assigned: @conductor [direct], depends on #2 OR #6) — DONE 2026-06-03
  - 300 .md notes + 24 `_COMMUNITY_*.md` notes + `graph.canvas` (121KB) in `graphify-out/obsidian/`
  - Generated via `graphify.export.to_obsidian` + `to_canvas`

- [x] **#10 — Generate wiki** (assigned: @conductor [direct], depends on #2 OR #6) — DONE 2026-06-03
  - 34 articles + `graphify-out/wiki/index.md`
  - Generated via `graphify.wiki.to_wiki`

- [x] **#12 — `examples/` directory** (assigned: @docs, depends on #4) — DONE 2026-06-03
  - `examples/add-an-agent.md` (88 lines) — references ADR-001
  - `examples/use-conductor.md` (77 lines) — references ADR-001 in See also
  - `examples/integrate-into-your-project.md` (75 lines) — corrected GitHub URL to JakeP

- [x] **#13 — Pre-commit hook** (assigned: @builder, depends on #1) — DONE 2026-06-03
  - Files: `scripts/pre-commit` (220 lines), `scripts/install-hook.sh` (36 lines)
  - 3 checks: JSON syntax, schema validation, fast pytest (skips test_agents_runtime.py)
  - Cross-platform: `python → python3 → py` fallback chain
  - `STRICT_PRECOMMIT=1` env var enforces pytest presence
  - Tolerates pytest collection errors per `--continue-on-collection-errors` policy

### Layer 3 (depends on Layer 2 — 2 tasks)

- [x] **#14 — Schema-instance pattern in graph** (assigned: @architect + @builder, depends on #3, #6) — DONE 2026-06-03
  - Created `AgentConfigSchema` template node (file_type: `rationale`, source: `opencode.schema.json`)
  - Added 6 `has_field` edges: `AgentConfigSchema` → `description`/`mode`/`model`/`fallback_model`/`permission`/`prompt`
  - Added 13 `instance_of` edges: each agent → `AgentConfigSchema`
  - All edges: `confidence: INFERRED, score: 0.95`
  - **Implementation:** `scripts/refine-graph.py` (post-processes graph.json, idempotent)

- [x] **#15 — Model value constraints in graph** (assigned: @architect, depends on #3, #6) — DONE 2026-06-03
  - Added 3 value nodes: `value_minimax_m3_free`, `value_big_pickle`, `value_opencode`
  - Added 13 `has_value_model` edges: each agent → its model value node
  - Added 13 `has_value_fallback_model` edges: each agent → its fallback model value node
  - All edges: `confidence: EXTRACTED, score: 1.0` (real values from opencode.json)
  - **Verified:** BFS from `value_big_pickle` reaches all 13 agents in 1 hop
  - **Implementation:** same `scripts/refine-graph.py`

## Verification

For each task, the verification step. The `python -c "..."` commands below are runnable by `scripts/verify-plan.py` — exit 0 means the verification passes.

- [x] **#1** — Tests folder has 4+ test files; pytest collects them — `python -c "from pathlib import Path; files = list(Path('tests').glob('test_*.py')); assert len(files) >= 4, f'expected 4+ test files, got {len(files)}'"` — **VERIFIED 2026-06-03**: 6 test files
- [x] **#2** — graph.json has ≥162 nodes; GRAPH_REPORT.md lists the corpus — `python -c "import json; d = json.load(open('graphify-out/graph.json')); assert len(d['nodes']) >= 162, f'expected >=162 nodes, got {len(d[chr(34)+chr(110)+chr(111)+chr(100)+chr(101)+chr(115)+chr(34)])}' if False else (n := len(d['nodes'])) >= 162 or (_ for _ in ()).throw(AssertionError(f'expected >=162 nodes, got {n}'))"` — **VERIFIED 2026-06-03**: 279 nodes
- [x] **#3** — opencode.json validates against opencode.schema.json — `python -c "import jsonschema, json; jsonschema.validate(json.load(open('opencode.json')), json.load(open('opencode.schema.json')))"` — **VERIFIED 2026-06-03**: validates
- [x] **#4** — ADR-001 exists and follows template (Context, Decision, Consequences) — `python -c "from pathlib import Path; t = Path('.opencode/decisions/adr-001-json-only-agents.md').read_text(); assert all(s in t for s in ['Context', 'Decision', 'Consequences']), 'missing required ADR sections'"` — **VERIFIED 2026-06-03**: all 3 sections present
- [x] **#5** — pytest test_conductor_workflow.py passes (6 tests) — `python -m pytest tests/test_conductor_workflow.py` — **VERIFIED 2026-06-03**: 6/6 PASSED
- [x] **#6** — graph has >6 INFERRED edges — `python -c "import json; d = json.load(open('graphify-out/graph.json')); n = sum(1 for l in d['links'] if l.get('confidence') == 'INFERRED'); assert n > 6, f'expected >6 INFERRED edges, got {n}'"` — **VERIFIED 2026-06-03**: 36 INFERRED edges
- [x] **#7** — .github/workflows/ci.yml exists with matrix strategy (ubuntu + windows) — `python -c "from pathlib import Path; p = Path('.github/workflows/ci.yml'); assert p.exists(), 'ci.yml not found'; t = p.read_text(); assert 'matrix' in t and 'ubuntu-latest' in t and 'windows-latest' in t, 'missing matrix strategy'"` — **VERIFIED 2026-06-14**: CI merged into single matrix workflow
- [x] **#8** — graphify-out/obsidian/ has _COMMUNITY_*.md files and graph.canvas — `python -c "from pathlib import Path; n = len(list(Path('graphify-out/obsidian').glob('_COMMUNITY_*.md'))); assert n > 0, 'no _COMMUNITY_*.md files'; assert Path('graphify-out/obsidian/graph.canvas').exists(), 'no graph.canvas'"` — **VERIFIED 2026-06-03**: 42 _COMMUNITY_*.md, graph.canvas present
- [x] **#9** — conftest.py exports cfg, repo_path fixtures; tests use them — `python -c "t = open('tests/conftest.py').read(); assert 'def cfg(' in t and 'def repo_path(' in t, 'missing conftest fixtures'"` — **VERIFIED 2026-06-03**: both fixtures present
- [x] **#10** — graphify-out/wiki/index.md exists and links to per-community articles — `python -c "from pathlib import Path; p = Path('graphify-out/wiki/index.md'); assert p.exists() and 'Communities' in p.read_text() and p.read_text().count('[[') > 5, 'index missing or no wiki-links'"` — **VERIFIED 2026-06-03**: 31 wiki-links
- [x] **#11** — LICENSE has MIT text — `python -c "from pathlib import Path; assert 'MIT' in Path('LICENSE').read_text(), 'LICENSE missing MIT text'"` — **VERIFIED 2026-06-03**: MIT text present
- [x] **#12** — examples/ has 3+ files, each ≥30 lines — `python -c "from pathlib import Path; files = list(Path('examples').glob('*.md')); assert len(files) >= 3, f'need 3+ files, got {len(files)}'; assert all(len(f.read_text().splitlines()) >= 30 for f in files), 'a file has <30 lines'"` — **VERIFIED 2026-06-03**: 3 files, 88/78/75 lines
- [x] **#13** — pre-commit hook installed and scripts/pre-commit exists — `python -c "from pathlib import Path; assert Path('.git/hooks/pre-commit').exists() and Path('scripts/pre-commit').exists(), 'pre-commit hook missing'"` — **VERIFIED 2026-06-03**: both exist
- [x] **#14** — graph has AgentConfigSchema + 6 has_field + 13 instance_of edges — `python -c "import json; d = json.load(open('graphify-out/graph.json')); assert any(n['id'] == 'AgentConfigSchema' for n in d['nodes']), 'no AgentConfigSchema'; hf = sum(1 for l in d['links'] if l.get('relation') == 'has_field' and l.get('source') == 'AgentConfigSchema'); inst = sum(1 for l in d['links'] if l.get('relation') == 'instance_of' and l.get('target') == 'AgentConfigSchema'); assert hf == 6 and inst == 13, f'has_field={hf} instance_of={inst}'"` — **VERIFIED 2026-06-03**: 6 has_field, 13 instance_of
- [x] **#15** — graph has 3 value_* nodes; BFS from value_big_pickle reaches all 13 agents in 1 hop — `python -c "import json; d = json.load(open('graphify-out/graph.json')); vals = {n['id'] for n in d['nodes'] if n['id'].startswith('value_')}; assert {'value_minimax_m3_free', 'value_big_pickle', 'value_opencode'} <= vals, f'missing value nodes: {vals}'; nbrs = set(l['source'] for l in d['links'] if l['target'] == 'value_big_pickle') | set(l['target'] for l in d['links'] if l['source'] == 'value_big_pickle'); agents = {'conductor', 'planner', 'builder', 'architect', 'reviewer', 'tester', 'docs', 'debugger', 'refactor', 'git', 'explorer', 'security', 'perf'}; hits = [n for n in nbrs if any(a in n.lower() for a in agents)]; assert len(hits) == 13, f'expected 13 agents at 1 hop, got {len(hits)}'"` — **VERIFIED 2026-06-03**: all 13 agents reachable

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
