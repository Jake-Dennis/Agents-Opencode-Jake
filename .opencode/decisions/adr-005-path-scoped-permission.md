# ADR 005: Path-Scoped Permission Pattern

- **Date:** 2026-06-08
- **Status:** Accepted
- **Deciders:** conductor, @architect
- **Supersedes:** ADR-004 (extends the permission model)

## Context

Plan-013 introduced live progress tracking via `.opencode/jobs.md`. The 5 read-only agents (planner, architect, reviewer, explorer, security) needed write access to exactly one file — `jobs.md` — while all other files remained read-only. The existing permission model only supported two forms:

1. `"allow"` — unrestricted access to a tool type
2. `"deny"` — complete denial of a tool type

Neither worked: `"allow"` would give these agents full write access (violating their security model), and `"deny"` would prevent them from writing to `jobs.md` (breaking the live progress feature).

The git agent already had a third form for `bash`: `{"git *": "allow", "*": "deny"}` — a path-scoped object where specific command patterns are allowed and everything else denied. Plan-013 extended this pattern to `edit`.

## Decision

Extend the permission model with a **path-scoped object form** for sub-keys (`edit`, `bash`, `webfetch`, `task`, `read`, `write`, etc.):

### Form 1: Scalar `"allow"`

```json
"edit": "allow"
```

Grants unrestricted access to all operations of this type. Used by the 6 implementation agents (builder, tester, docs, debugger, refactor, perf).

### Form 2: Scalar `"deny"`

```json
"edit": "deny"
```

Denies all operations of this type. Used by any agent that should not perform this action.

### Form 3: Path-scoped object

```json
"edit": {
  ".opencode/jobs.md": "allow",
  "*": "deny"
}
```

Grants access to specific paths/patterns while denying everything else. The `*` key is a catch-all glob that matches any path not explicitly listed. Paths are literal (no wildcard characters beyond `*`). Case-sensitivity follows the platform default (case-insensitive on Windows).

### Semantics

1. The object is evaluated from top-to-bottom. The first matching key wins.
2. `"*"` is the default catch-all. If omitted, paths not matching an explicit key default to `"ask"` (the opencode default).
3. The form can be nested per-tool (`edit`, `bash`, etc.) and each tool has its own independent policy.
4. This form mirrors the upstream `permission` block pattern used for global config: `{"edit": "ask", "bash": {"rm -rf *": "deny", "*": "ask"}}`.

## Consequences

**Positive:**
- 5 read-only agents can now write to `jobs.md` while staying locked down for everything else
- Pattern is consistent with the existing git agent's `bash` permission
- Testable: T-JB-3 verifies the `edit` object for all 5 agents

**Negative:**
- The `*` catch-all glob syntax is undocumented in upstream opencode docs (per plan-013 risk analysis). If upstream changes the semantics, the pattern may break.
- Paths are relative to the repo root; an agent could theoretically write to other files matching the same literal path (low risk since `jobs.md` is a unique filename in `.opencode/`).

**Neutral:**
- This pattern can be extended to other permission keys (`read`, `webfetch`, etc.) if a future use case requires it.
- The git agent's `bash` pattern should also be migrated to this form for consistency (see plan-014 item #4).
