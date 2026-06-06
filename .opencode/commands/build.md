---
description: Execute all plans to completion. Continuously builds, tests, verifies, and archives each plan in a loop until every plan is done.
---

Enter BUILD LOOP mode. Your goal: execute ALL plans in .opencode/plans/ to completion. Do NOT stop until every plan is archived to .opencode/plans/completed/. Follow this exact loop:

1. SCAN — list all files in .opencode/plans/ that are NOT in the completed/ subfolder. Read each one and check its Status line.
2. CHECK — if no in-progress plans remain, break the loop and go to step 9.
3. SELECT — pick the plan with the lowest NNN number. If there are multiple, ask the user which to prioritize.
4. EXECUTE — for the selected plan, run its incomplete tasks layer by layer using parallel dispatch. Follow the conductor's standard dispatch workflow (step 5 from the workflow). After each layer, dispatch @reviewer to verify the output (conductor's step 7). Wait for each layer (dispatch + review) to complete before starting the next.
5. BUILD — compile the project. Detect the build system automatically: if package.json run 'npm run build' (or 'yarn build' / 'pnpm build'), if Cargo.toml run 'cargo build', if go.mod run 'go build ./...', if setup.py/pyproject.toml try 'python -m build' or 'pip install -e .', if Makefile run 'make'. If the build fails, dispatch @debugger and @builder to fix errors, then re-run the build. Do NOT proceed until the build passes.
6. TEST — run the test suite. Detect the test system: if package.json run 'npm test' (or 'yarn test' / 'pnpm test'), if Cargo.toml run 'cargo test', if go.mod run 'go test ./...', if pytest is detected run 'python -m pytest', if Makefile run 'make test'. If tests fail, dispatch @debugger to diagnose and @builder to fix, then re-run tests. Loop until all tests pass.
7. VERIFY — re-read the plan file. For each checked task, confirm the result in the actual codebase. Files that should exist DO exist. Tests that should pass DO pass. Review that was done was APPROVED.
7.5. MECHANICAL VERIFY (HARD GATE — CANNOT SKIP) — run `python scripts/verify-plan.py <plan-file>` where `<plan-file>` is the path to the active plan. If exit code is non-zero, STOP IMMEDIATELY. Do NOT proceed to ARCHIVE. Do NOT mark the plan as complete. Dispatch @debugger to fix any failing verifications, then re-run this step. This step is what makes verification ACTUALLY happen — it is not optional, not advisory, not a 'trust the subagent' check. The script runs every `- [x] #N - \`command\`` line from the plan's `## Verification` section and exits 0 only if all commands pass. NEVER bypass this step. NEVER mark tasks verified by hand.
8. ARCHIVE — only after step 7.5 exits 0, update the plan Status to Complete, record the timestamp, move the file to .opencode/plans/completed/. Append a work-log entry. Then loop back to step 1.
9. REPORT — when all plans are complete, give the user a summary of everything built, tested, and archived.
10. GIT — stage all changes with 'git add -A', draft a descriptive commit message covering all completed plans, and ask the user if they want to push.
