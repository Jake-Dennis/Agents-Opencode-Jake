# TODO

All tasks complete. No pending work.

## Completed
- [x] Plan 016: 10 structural improvements (externalize prompts, CI merge, verify-plan checks, /status command, etc.)
- [x] Plan 017: 10 agent quality improvements (shared sections, per-agent specialization, context protocol, etc.)
- [x] Harden graphify context passing (dispatch template, MANDATORY precondition, one-liner on all 13 agents)
- [x] Plan 001: Conductor owns graphify queries; subagents consume (supersedes the soft "MANDATORY" line-1 in b6f0a52 with a hard architectural split; missing `Graph context:` block is now a visible dispatch failure)

## Pre-existing issues (not in scope)
- [ ] T_AS_1 / T_AS_5: Tests expect `steps` field on agents, but agents don't have `steps` (either add `steps` or remove tests)