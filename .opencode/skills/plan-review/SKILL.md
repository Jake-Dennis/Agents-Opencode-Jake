---
name: plan-review
description: Use when reviewing a plan or subagent output against the Momus 4-criteria rubric (correctness, specification, clarity, operability). Invoke before approving a plan, before /build commits it, or whenever a subagent's claim needs sanity-checking. Avoid for casual code review of in-flight code — use the `reviewer` agent for that.
---

# Plan Review (Momus 4-Criteria Rubric)

This skill is the canonical review checklist for plans, subagent deliverables, and any artifact that the conductor is about to commit. It is the qualitative sibling of the 5 mechanical checks in `verify-plan-gate` — together they form a two-layer gate.

## When to use

Invoke this skill any time a subagent reports completion of a multi-step plan task, or any time a plan moves from PLANNED to IN PROGRESS. The 4-criteria rubric is intentionally fast (5-10 min per plan) because the 5 mechanical checks already caught the structural errors; this rubric catches the "looks right but is wrong" failures.

## Process / Checklist

Score the artifact on 4 axes. Each is pass/fail. A single fail means the plan is REJECTED, not approved-with-nits.

### 1. Correctness
- Does the code/plan do what the spec says it should do?
- Are the inputs/outputs of every function/file match the spec?
- Is the math right (counts, indices, sizes, regex quantifiers)?
- Are the dependencies actually used (no dead `import`s)?

**Pass example:** the plan claims to "add 5 tests" and the test file actually has 5 new `def test_*` functions.
**Fail example:** the plan claims "extracted to 3 markdown files" but only 2 were created.

### 2. Specification
- Does the artifact match the plan's T-spec for that task?
- If the architect's design doc exists, do the file paths and field names match?
- Are all required deliverables present (no "TODO: implement later" left in)?
- Are edge cases from the spec handled (empty input, missing file, collision)?

**Pass example:** T-spec said "5 tests T-SK-1..T-SK-5" and the test file has exactly 5 test functions with those names.
**Fail example:** T-spec said "frontmatter with name + description" but the file has a third undocumented key.

### 3. Clarity
- Is the artifact readable by the next person (or future-you) without the original spec in hand?
- Are variable names, file names, and section headers descriptive?
- Are non-obvious decisions commented?
- Is the commit message self-contained (no "see PR #123 for context")?

**Pass example:** the test file's docstring explains what each test class covers.
**Fail example:** the test file has 20 tests named `test_1`, `test_2`, ..., `test_20`.

### 4. Operability
- Can the conductor run `verify-plan.py` and `pytest` against the artifact and get a clean result?
- Are the file paths portable (no Windows-only or Unix-only assumptions)?
- Is the test file stdlib-only (or has it declared its deps)?
- Does the commit leave the repo in a runnable state (no half-applied changes)?

**Pass example:** `python -m pytest tests/test_skills.py -v` exits 0.
**Fail example:** the test file imports `pyyaml` but the project doesn't list it in any deps.

## Examples

### Worked example: plan-007 verify-plan.py review

T-spec said: "add 5 mechanical checks to `verify-plan.py`". Reviewer scored:

- **Correctness:** PASS — all 5 checks are present, each with a clear regex/string pattern.
- **Specification:** PASS — the 5 checks are exactly the 5 listed in the T-spec.
- **Clarity:** PASS — each check has a docstring explaining what it looks for and why.
- **Operability:** FAIL — the script uses `re.search` against line numbers but the LLM-generated plans have CR/LF line ending issues on Windows. Reviewer flagged: "wrap the verify script in a try/except for `UnicodeDecodeError`".

The plan was REJECTED, not approved-with-nits. The script was updated; second review was clean.

### Anti-example: "I trust the subagent"

Common failure mode: the LLM sees `@builder: Done, 10/10 tests passing` and writes "build approved" to the work-log. Without the rubric, the LLM skips verification. With the rubric, the LLM asks: "Did the builder actually run the tests, or just claim they pass?" Operability check #1 (can I re-run pytest and get 10/10?) is the cure.

## Common pitfalls

- **Pitfall 1: "Approved with nits"** — the rubric is pass/fail, not graded. A nit IS a fail. Reject, fix, re-review.
- **Pitfall 2: Skipping operability** — the easiest check to skip ("I trust the tests passed"). Always re-run `verify-plan.py` and `pytest` yourself. The `verify-plan-gate` skill's 3-layer enforcement is the structural fix.
- **Pitfall 3: Reviewing the spec, not the artifact** — the artifact is what gets committed, not the spec. Read both, but score the artifact.
