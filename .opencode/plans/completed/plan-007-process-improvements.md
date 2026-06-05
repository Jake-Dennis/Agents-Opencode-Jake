# Plan 007: Process Improvements (Tier 1 + 2)

## Goal
Three small improvements that fit the project's priorities (single-model, auditability, plan-as-artifact, ADRs, mechanical verify gates):
1. Commit the `+  "$schema"` line in `opencode.json` (1-line chore, IDE support)
2. Document agent role boundaries (`.opencode/decisions/adr-004-agent-roles.md` + `AGENT-ROLES.md`)
3. Add stricter `scripts/verify-plan.py` rules — reframe Momus's 4-criteria rubric as MECHANICAL checks (fits priority #5, rejects LLM-judgment)

## Tasks

### Layer 1 (parallel, no deps)
- [ ] #1: @docs writes `.opencode/decisions/adr-004-agent-roles.md` AND `AGENT-ROLES.md` (assigned: @docs)
- [ ] #2: @builder modifies `scripts/verify-plan.py` to add 5 mechanical checks + writes tests in `tests/test_verify_plan.py` (assigned: @builder)

### Layer 2 (depends on Layer 1)
- [ ] #3: @reviewer reviews all changes (verify-plan.py + tests + docs + ADR) (assigned: @reviewer)

### Layer 3 (conductor, depends on Layer 2)
- [ ] #4: @conductor fixes any review nits, marks plan-007 complete, archives, commits the `$schema` chore (assigned: @conductor)

## T1 Spec (docs)
Read first:
- `.opencode/decisions/adr-003-graphify-auto-refresh.md` (match ADR format)
- `.opencode/opencode.json` (get the agent list + permissions)
- `AGENTS.md` if it exists (check for existing role doc)

Two files to write:
1. **`.opencode/decisions/adr-004-agent-roles.md`** (200-500 lines, ADR format with Context, Decision, Alternatives, Consequences, Pros/Cons, References)
2. **`AGENT-ROLES.md`** at repo root (100-200 lines, table-based reference)

For each of the 13 agents (conductor, planner, builder, architect, reviewer, tester, docs, debugger, refactor, git, explorer, security, perf):
- Role: 1-sentence purpose
- Can: bullet list of actions
- Cannot: bullet list of restrictions
- Owned by: which lifecycle phase (Orchestration, Planning, Implementation, Review, Documentation, Operations, Read-only, Specialized)

## T2 Spec (verify-plan.py + tests)
Read first:
- `scripts/verify-plan.py` (the existing 209-line script)
- `tests/test_graphify_refresh.py` (most recent test pattern)

5 mechanical checks to add (each must be a regex / string check, NOT LLM judgment):

1. **`@-assignment check`**: Every task line in `### Layer N` sections contains `@-agent` (regex: `(?<!\S)@\w+`).
2. **Non-empty description check**: Every task line has 10+ chars of content after the @-assignment.
3. **Verification coverage check**: The `## Verification` section has at least N entries where N = number of `### Layer N` sections.
4. **No duplicate task IDs**: No two `#N` numbers in the `## Verification` section are the same.
5. **Cross-reference resolution**: Any explicit ref or backticked `.md`/`.py`/`.json` path in the plan resolves to an existing file (relative to repo root).

Implementation:
- New function `run_mechanical_checks(plan_path)` in verify-plan.py
- Call it from `main()` after the existing task loop
- New report section titled "MECHANICAL CHECKS" with PASS/FAIL per check
- If any fails, exit code 1 (use existing exit logic)

Tests in `tests/test_verify_plan.py` (new file, stdlib only, use `subprocess.run` to invoke script):
- T-MC-1: Valid plan (all 5 checks satisfied) → script exits 0
- T-MC-2: Plan missing @-assignment → check 1 fails
- T-MC-3: Plan with short description → check 2 fails
- T-MC-4: Plan with too few verification entries → check 3 fails
- T-MC-5: Plan with duplicate task IDs → check 4 fails
- T-MC-6: Plan with unresolved cross-reference → check 5 fails

Constraints:
- Stdlib only, no new dependencies
- Existing 86 tests must still pass
- Run `python -m pytest tests/ -q` at the end to verify all tests pass

## Verification
- [ ] #1: `python -c "import os; assert os.path.exists('.opencode/decisions/adr-004-agent-roles.md') and 30 <= len(open('.opencode/decisions/adr-004-agent-roles.md', encoding='utf-8').readlines()) <= 500"`
- [ ] #2: `python -c "import os; assert os.path.exists('AGENT-ROLES.md') and 30 <= len(open('AGENT-ROLES.md', encoding='utf-8').readlines()) <= 300"`
- [ ] #3: `python -c "import os; assert os.path.exists('scripts/verify-plan.py') and 'MECHANICAL CHECKS' in open('scripts/verify-plan.py', encoding='utf-8').read()"`
- [ ] #4: `python -c "import os; assert os.path.exists('tests/test_verify_plan.py') and 30 <= len(open('tests/test_verify_plan.py', encoding='utf-8').readlines()) <= 800"`
- [ ] #5: `python scripts/verify-plan.py .opencode/plans/completed/plan-001-improve-project.md` exits 0
- [ ] #6: `python -c "import subprocess, sys, re; r = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=no'], capture_output=True, text=True, timeout=300); out = r.stdout + ' ' + r.stderr; m = re.search(r'(\d+) passed', out); assert m and int(m.group(1)) > 86, f'need > 86 passed, got: {out[-500:]}'"` shows "X passed" with X > 86

## Deliverables
- `.opencode/decisions/adr-004-agent-roles.md` (new, 200-500 lines)
- `AGENT-ROLES.md` (new at repo root, 100-200 lines)
- `scripts/verify-plan.py` (modified, +100-200 lines for new checks)
- `tests/test_verify_plan.py` (new, 200-800 lines for 5+ tests)
- `$schema` line in `opencode.json` (committed as chore)
