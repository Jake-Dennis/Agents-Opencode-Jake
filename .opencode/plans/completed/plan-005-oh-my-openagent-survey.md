# Plan 005: oh-my-openagent Light Survey

## Goal
Produce a 1-2 page research note on each of four oh-my-openagent mechanisms: (1) boulder.json + session resume, (2) team_mode code, (3) notepads system, (4) category-based routing. Light survey only — not deep code analysis. Output is a research deliverable for the user to decide which ideas (if any) to adopt into Agents-Opencode-Jake. No code changes to the project.

## Historical context
- ADR-001 (`json-only-agents.md`) notes that the project's *agent definition* style was originally inspired by oh-my-openagent (dual-source: `.md` + `.json`), but the project explicitly moved AWAY from that pattern to a single-source JSON approach. So this project has a track record of picking-and-choosing from oh-my-openagent, not copying wholesale.
- The 4 areas surveyed here are unrelated to that earlier decision.

## Tasks

### Layer 1 (parallel, no deps)
- [ ] T1: Research boulder.json + session resume (assigned: @general)
- [ ] T2: Research team_mode code (assigned: @general)
- [ ] T3: Research notepads system (assigned: @general)
- [ ] T4: Research category-based routing (assigned: @general)

### Layer 2 (depends on Layer 1)
- [ ] T5: Synthesize into SUMMARY.md (assigned: @docs)

## Verification
- [x] #1 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/boulder.md'; assert os.path.exists(p) and 30 <= len(open(p).readlines()) <= 400"`
- [x] #2 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/team-mode.md'; assert os.path.exists(p) and 30 <= len(open(p).readlines()) <= 400"`
- [x] #3 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/notepads.md'; assert os.path.exists(p) and 30 <= len(open(p).readlines()) <= 400"`
- [x] #4 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/category-routing.md'; assert os.path.exists(p) and 30 <= len(open(p).readlines()) <= 400"`
- [x] #5 - `python -c "import os; p='.opencode/research/oh-my-openagent-survey/SUMMARY.md'; assert os.path.exists(p) and 30 <= len(open(p).readlines()) <= 500"`

## Deliverables
- `.opencode/research/oh-my-openagent-survey/boulder.md`
- `.opencode/research/oh-my-openagent-survey/team-mode.md`
- `.opencode/research/oh-my-openagent-survey/notepads.md`
- `.opencode/research/oh-my-openagent-survey/category-routing.md`
- `.opencode/research/oh-my-openagent-survey/SUMMARY.md`
