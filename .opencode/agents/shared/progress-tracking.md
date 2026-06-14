## Live progress tracking

As you work, update `.opencode/jobs.md` so the conductor and the user can see live status. Rules:

1. **Start**: append a new entry `## [<plan-id>] @<your-name> - <task>` with Status: `in_progress`, the timestamp, and the first sub-step marked `[~]`.
2. **As you work**: update `Last update` and `Current step`; flip sub-steps `[ ]` -> `[~]` -> `[x]`.
3. **Finish**: set Status: `complete` (or `failed`/`blocked`); mark the last sub-step `[x]`.

The exact format and a worked example are in `.opencode/jobs.md` (the comment block at the top). Keep entries short — jobs.md is for status, work-log.md is for detail.