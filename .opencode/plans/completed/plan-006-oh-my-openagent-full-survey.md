# Plan 006: oh-my-openagent Full Survey

## Goal
Comprehensive survey of oh-my-openagent covering (1) deepened analysis of the 4 already-surveyed areas, (2) all 11 agents, (3) the orchestration shell. Output is a research deliverable (~20 pages) for the user to make informed decisions about adoption. No code changes to the project.

## Context
- The light survey (plan-005) produced 5 docs covering 4 areas. SUMMARY verdict: do not adopt any of 4 verbatim; the multi-work `works` map is the one transferable idea.
- The full survey adds depth to the 4 areas and broadens coverage to the 11 agents and orchestration shell that plan-005 did not touch.
- Repo: https://github.com/code-yeongyu/oh-my-openagent (dev branch). Same as plan-005. Note: oh-my-opencode and oh-my-openagent are the same project (mid-rename).
- File structure: deepen-existing docs go in `full/{area}-deep.md`; new surveys go in `full/agents-*.md` and `full/orchestration-*.md`; synthesis goes in `full/FINAL_SUMMARY.md`. The light survey docs are NOT modified.

## Tasks

### Layer 1 (parallel, no deps) — deepen 4 areas
- [x] #1 - Deepen boulder.json (assigned: @general) — read boulder.md, write 400-600 lines
- [x] #2 - Deepen team_mode (assigned: @general) — read team-mode.md, write 300-500 lines
- [x] #3 - Deepen notepads (assigned: @general) — read notepads.md, write 300-500 lines
- [x] #4 - Deepen category-routing (assigned: @general) — read category-routing.md, write 400-600 lines

### Layer 2 (parallel, no deps) — survey 11 agents
- [x] #5 - Survey "doer" agents: Sisyphus, Sisyphus-Junior, Hephaestus (assigned: @general) — 1-2 pages
- [x] #6 - Survey "planner/reviewer" agents: Prometheus, Momus, Metis (assigned: @general) — 1-2 pages
- [x] #7 - Survey "executor/verifier" agents: Atlas, Oracle (assigned: @general) — 1-2 pages
- [x] #8 - Survey "support" agents: Librarian, Explore, Multimodal-Looker (assigned: @general) — 1-2 pages

### Layer 3 (parallel, no deps) — survey orchestration shell
- [x] #9 - Workflow loop: plan-gen -> plan-review -> plan-execute -> plan-verify (assigned: @general) — 1-2 pages
- [x] #10 - `ulw` keyword, slash commands, keyword-driven dispatch (assigned: @general) — 1-2 pages
- [x] #11 - Skills, hooks, plugin architecture, MCPs (assigned: @general) — 1-2 pages
- [x] #12 - CLI, configuration, model provider setup, telemetry (assigned: @general) — 1-2 pages

### Layer 4 (depends on Layers 1-3) — synthesis
- [x] #13 - FINAL_SUMMARY.md synthesis of all 12 docs (assigned: @docs) — 3-5 pages

## Verification
For each task, the file should exist with appropriate line count:
- [x] #1 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/boulder-deep.md'; assert os.path.exists(p) and 200 <= len(open(p, encoding='utf-8').readlines()) <= 700"`
- [x] #2 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/team-mode-deep.md'; assert os.path.exists(p) and 200 <= len(open(p, encoding='utf-8').readlines()) <= 700"`
- [x] #3 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/notepads-deep.md'; assert os.path.exists(p) and 200 <= len(open(p, encoding='utf-8').readlines()) <= 700"`
- [x] #4 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/category-routing-deep.md'; assert os.path.exists(p) and 200 <= len(open(p, encoding='utf-8').readlines()) <= 700"`
- [x] #5 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/agents-doers.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #6 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/agents-planners.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #7 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/agents-executor-verifier.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #8 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/agents-support.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #9 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/orchestration-workflow.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #10 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/orchestration-keywords.md'; assert os.path.exists(p) and 30 <= len(open(p, encoding='utf-8').readlines()) <= 400"`
- [x] #11 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/orchestration-skills-hooks.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #12 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/orchestration-cli-config.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 500"`
- [x] #13 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/full/FINAL_SUMMARY.md'; assert os.path.exists(p) and 50 <= len(open(p, encoding='utf-8').readlines()) <= 1000"`

## Deliverables
- `.opencode/research/oh-my-openagent-survey/full/boulder-deep.md`
- `.opencode/research/oh-my-openagent-survey/full/team-mode-deep.md`
- `.opencode/research/oh-my-openagent-survey/full/notepads-deep.md`
- `.opencode/research/oh-my-openagent-survey/full/category-routing-deep.md`
- `.opencode/research/oh-my-openagent-survey/full/agents-doers.md`
- `.opencode/research/oh-my-openagent-survey/full/agents-planners.md`
- `.opencode/research/oh-my-openagent-survey/full/agents-executor-verifier.md`
- `.opencode/research/oh-my-openagent-survey/full/agents-support.md`
- `.opencode/research/oh-my-openagent-survey/full/orchestration-workflow.md`
- `.opencode/research/oh-my-openagent-survey/full/orchestration-keywords.md`
- `.opencode/research/oh-my-openagent-survey/full/orchestration-skills-hooks.md`
- `.opencode/research/oh-my-openagent-survey/full/orchestration-cli-config.md`
- `.opencode/research/oh-my-openagent-survey/full/FINAL_SUMMARY.md`
