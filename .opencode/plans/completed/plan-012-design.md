# Plan 012 Design: Per-agent color + temperature + top_p + variant

## Section 1: Color matrix (13 agents, 4-color semantic groups)

13 distinct colors, semantically grouped. Colors use 4 of the 8 theme names (`primary`/`secondary`/`accent`/`success`/`warning`/`error`/`info`) and 3 hex codes for differentiation within groups.

| Agent | color | Reasoning |
|---|---|---|
| `conductor` | `#5EEAD4` (teal) | Orchestrator — distinct, calm, "default" feel |
| `planner` | `#A78BFA` (purple) | Planning — distinct from implementation |
| `builder` | `#34D399` (green) | Implementation — "go/build" |
| `reviewer` | `#FBBF24` (amber) | Review — "caution, look closely" |
| `tester` | `#60A5FA` (blue) | Testing — "info/verify" |
| `architect` | `#C4B5FD` (lavender) | Architect — same family as planner (planning phase) |
| `docs` | `#F472B6` (pink) | Documentation — accent, friendly |
| `debugger` | `#F87171` (red) | Debugging — "fix this" |
| `refactor` | `#6EE7B7` (mint) | Refactor — same family as builder (implementation) |
| `git` | `#94A3B8` (slate) | Operations — neutral, "infrastructure" |
| `explorer` | `#7DD3FC` (sky) | Read-only — "info/navigate" |
| `security` | `#DC2626` (dark-red) | Security — "be careful, critical" |
| `perf` | `#F59E0B` (orange) | Performance — "measure, optimize" |

**13 distinct hex colors, 6 of which are pastel/varied to keep the TUI legible.** All hex codes are valid (`^#[0-9a-fA-F]{6}$`).

**Color groupings (semantic):**
- **Implementation (warm-greens):** builder, refactor
- **Review (warning/amber):** reviewer, perf
- **Read-only (cool-blues):** tester, explorer
- **Planning (purples):** planner, architect
- **Operations (slate/red/pink):** conductor, git, docs, debugger, security

**Why not theme names?** The 8 theme names (`primary`/`secondary`/`accent`/`success`/`warning`/`error`/`info`) only give 8 distinct values, but we want 13 distinct agents. Using hex codes for differentiation within a semantic group gives the right balance of "same family for related roles" and "distinct enough to tell apart in the TUI".

## Section 2: Temperature matrix (4 agents only)

Per the plan's recommendation, add `temperature` to a small subset where determinism is critical. Most agents use the model default.

| Agent | temperature | Reasoning |
|---|---|---|
| `reviewer` | `0.1` | Mechanical checklist; deterministic scoring. The reviewer's prompt already says "run verify-plan.py first"; low temperature makes the subsequent checklist more reproducible. |
| `security` | `0.1` | Audit report; deterministic, no false positives. Security findings should not vary by chance. |
| `planner` | `0.2` | Plan should be predictable, not creative. Plans are constraints + layers, not prose poetry. |
| `architect` | `0.2` | Design should be predictable. Same rationale as planner. |
| (9 others) | (omitted) | Use model default; `reasoning_effort: max` (set globally in `provider.opencode.options`) is the primary override. |

**Why these 4 specifically?** They are the agents where the output is a "report" or "design" — text artifacts that benefit from determinism. Code-writing agents (`builder`, `refactor`, `tester`) benefit from a bit of exploration; operations agents (`debugger`, `git`, `docs`, `explorer`, `security`-bash-asks, `perf`) are interactive and benefit from flexibility.

**Note:** setting `temperature` below the model default DOES interact with `reasoning_effort: max`. The interaction is provider-specific; some providers ignore `temperature` when `reasoningEffort` is set, others multiply. Test only checks the field is well-formed; behavior verification requires running opencode.

## Section 3: Top P matrix (mutually exclusive with temperature)

**Recommendation: skip `top_p` entirely.**

The plan says `temperature` and `top_p` are "mutually exclusive in practice" and "architect MAY choose one or the other; do not apply both to the same agent".

Reasoning:
- `temperature` scales the logits; `top_p` truncates the distribution. Both reduce randomness, but in different ways. Applying both to the same agent is redundant.
- The 4 agents in Section 2 already have `temperature` set. Adding `top_p` to the other 9 (the "default" set) would be applying it broadly, which is harder to reason about than 4 targeted `temperature` settings.
- The plan's T-AS-15 test enforces "no agent has BOTH temperature and top_p" — by skipping `top_p` for the 4 `temperature` agents and not adding it to the other 9, the test passes trivially.

If a future plan wants `top_p`, the matrix can be derived from this design doc by swapping the 4 `temperature` values for `top_p: 0.9` (the plan's suggested value).

## Section 4: Variant matrix (NOT APPLIED — model unverified)

**Decision: skip `variant` for this plan.**

**Why:**
1. **Model name `opencode/minimax-m3-free` is unverified.** The `opencode models` CLI crashes on this machine with `Failed to run the query 'CREATE TABLE project...'`. The model may or may not exist; the CLI cannot enumerate it. (See `.opencode/todo.md` and the plan-009/010 work-log entries for the full bug history.)
2. **Zen free-tier model variants are undocumented in the upstream docs.** Per the webfetch on https://opencode.ai/docs/models: built-in variants are listed for Anthropic (`high`/`max`), OpenAI (`none`/`minimal`/`low`/`medium`/`high`/`xhigh`), and Google (`low`/`high`). The `opencode` (Zen) provider has no documented built-in variants.
3. **Variants are silent no-ops if unsupported.** Per the plan: "Setting a wrong variant name is also silently ignored (no error)". So omitting is safe; setting incorrectly is a no-op (not a failure, but also not valuable).
4. **The plan explicitly says:** "If the model is unverifiable (CLI broken, docs unclear), err on the side of NOT setting `variant` and note in the design doc."

**What this plan delivers instead:**
- `color` on all 13 agents (visual, safe, reversible)
- `temperature` on 4 agents (determinism tuning, reversible)
- `variant` deferred to a future plan that can verify the model

**Future plan TODO:** once the model name is verified (either by fixing the CLI or by user clarification), add a `variant` section. Likely candidates: `reviewer`/`security` -> `low` (fast, deterministic), `planner`/`architect` -> `default` (let `reasoning_effort: max` drive). The values would need to be confirmed against the model's actual supported variants.

## Section 5: Risk analysis

- **Risk 1: `color` is invalid.** Mitigation: T-AS-11 checks each color against `^#[0-9a-fA-F]{6}$` (valid hex) or the 8 theme names. All 13 hex codes are valid.
- **Risk 2: `temperature` interaction with `reasoningEffort: max`.** The interaction is provider-specific; some providers ignore `temperature` when `reasoningEffort` is set, others multiply. Test only checks the field is well-formed. The values chosen (0.1-0.2) are conservative and should not BREAK reasoning — they just make the OUTPUT distribution narrower.
- **Risk 3: TUI rendering of pastel colors.** Some terminals may not render the pastel hex codes well. Mitigation: the colors are all from the standard "tailwind-200/300/400" palette, which is well-supported.
- **Risk 4: Pre-existing `reasoning_effort: max` is global.** Adding per-agent `temperature` may cause some agents to run at `temp=0.1 + reasoningEffort=max` and others at `model-default + reasoningEffort=max`. This is intentional and documented in Section 2.
- **Risk 5: 9 agents don't get a behavioral change.** Only 4 of 13 agents get `temperature`. The other 9 (including the most-executed: `builder`, `tester`, `debugger`) are unaffected. This is by design — the project values determinism for review-class agents and flexibility for implementation-class agents.
- **Risk 6: `opencode.schema.json` may not validate new fields.** The project-internal schema's `agentEntry` does not set `additionalProperties: false`, so the new `color`/`temperature` fields are schema-safe. T-AS-11..T-AS-15 provide the actual validation.

## Section 6: Field placement in opencode.json

Per the plan: "Maintain all existing fields. Place new fields in any position within the agent object (convention: after `permission`)."

For each of the 13 agents, the field order in `opencode.json` will be:
```
description -> mode -> steps -> permission -> [color] -> [temperature] -> prompt
```

`color` is added to all 13. `temperature` is added to 4 (after `color`). `prompt` stays last (it can be a long string and putting it last keeps the diff readable).

## Section 7: Test plan (T-AS-11..T-AS-15)

See plan body. 5 new tests appended to `tests/test_agent_safety.py`. All 15 tests (T-AS-1..T-AS-15) must pass.

| Test | Asserts |
|---|---|
| T-AS-11 | All 13 agents have a `color` field that is either a valid hex (`^#[0-9a-fA-F]{6}$`) or one of the 8 theme names. |
| T-AS-12 | For agents with a `temperature` field, the value is a number in [0.0, 2.0]. |
| T-AS-13 | For agents with a `top_p` field, the value is a number in [0.0, 1.0]. |
| T-AS-14 | For agents with a `variant` field, the value is a non-empty string. |
| T-AS-15 | No agent has BOTH `temperature` and `top_p` set (the plan's mutual-exclusivity rule). |

**Note on T-AS-13 and T-AS-14:** the architect's design does NOT add `top_p` or `variant` to any agent. T-AS-13 and T-AS-14 will pass trivially (no agent has the field). T-AS-15 also passes trivially (no agent has BOTH). These tests are forward-compatibility: if a future plan adds `top_p` or `variant`, the tests will catch invalid values.
