# Example: Use the conductor

This walkthrough shows how the conductor orchestrates a real task end-to-end.

## The setup

You have a Python project with a flaky test. You want to:
1. Reproduce the failure
2. Diagnose the root cause
3. Fix the bug
4. Add a regression test
5. Commit the fix

## How you'd say it to the conductor

> "My `tests/test_auth.py::test_login` is flaky. It passes locally but fails in CI. Please diagnose and fix."

## What the conductor does (14 steps)

1. **CLARIFY** — asks "Is the CI on GitHub Actions? What's the failure rate?" (you answer: "GitHub, ~30% failure rate")
2. **GRAPHIFY** — queries the knowledge graph for the test, auth module, and any related code
3. **PLAN** — writes `.opencode/plans/plan-001-fix-flaky-auth.md` with 3 layers:
   - Layer 1: `@debugger` reproduces + `@explorer` finds related code
   - Layer 2: `@builder` fixes the bug
   - Layer 3: `@tester` adds regression test + `@reviewer` checks
4. **TODO** — writes the same checklist to `.opencode/todo.md`
5. **DISPATCH** — sends `@debugger` and `@explorer` in parallel (Layer 1)
6. **TRACK** — marks Layer 1 tasks `in_progress` as they start
7. **REVIEW** — `@reviewer` checks the debug output and the code exploration
8. **VERIFY** — re-reads the plan, confirms the failure was reproduced
9. Layer 2 dispatched (`@builder` writes the fix)
10. Layer 3 dispatched (`@tester` adds regression + `@reviewer` approves)
11. **DOCUMENT** — appends to `.opencode/work-log.md`, creates ADR-002 if it's an interesting decision
12. **ARCHIVE** — moves the plan to `.opencode/plans/completed/`
13. **SYNC TODO** — flushes todo state
14. **GRAPHIFY UPDATE** — re-extracts the new code + test
15. **GIT** — stages, drafts commit, asks you to push
16. **REPORT** — summary of what was done

## What you see in your terminal

The conductor talks to you as it works. You can interrupt at any step. Example transcript:

```
conductor: I'll start by reproducing the failure.
@debugger — running tests/test_auth.py::test_login 3 times in a loop...
@debugger: Found it. Test fails when the JWT secret env var is unset in CI.
@debugger: The test expects auth to throw, but it actually creates a session.

conductor: Layer 1 complete. @explorer, what other tests use auth?
@explorer — found 3 tests that depend on auth: test_login, test_logout, test_admin

conductor: Layer 2: @builder, fix the bug.
@builder — edited src/auth.py to throw a clear error when JWT_SECRET is unset
@builder — added a "missing JWT_SECRET" check at the top of create_session

conductor: Layer 3: @tester, write a regression test.
@tester — added tests/test_auth.py::test_jwt_secret_required
@tester — confirmed test fails without JWT_SECRET, passes with it

conductor: @reviewer, approve?
@reviewer — APPROVED. The fix is minimal, the test covers the regression, the
   docstring explains why the env var is required.

conductor: Plan complete. Should I commit and push?
```

## Tips

- **Interrupt at any step** — the conductor pauses for your input between layers
- **Override the plan** — if you disagree with the approach, say "skip Layer 2, do X instead"
- **Inspect artifacts** — `.opencode/plans/plan-NNN-*.md` shows the plan, `.opencode/work-log.md` shows the audit trail

## See also

- `AGENTS.md` — agent descriptions
- `.opencode/plans/plan-001-improve-project.md` — example plan
- `.opencode/decisions/adr-001-json-only-agents.md` — why the conductor's prompt lives in `opencode.json` (not a separate `.md` file)
