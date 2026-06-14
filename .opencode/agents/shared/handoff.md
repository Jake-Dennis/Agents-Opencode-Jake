## Handoff format

When you finish a task, append a handoff block to your `.opencode/jobs.md` entry:

```
- **Changed files:** [list of files modified or created]
- **Trade-offs:** [1-2 sentences on what you chose and why]
- **Risks:** [what might break or needs follow-up]
```

This gives the next agent (reviewer, debugger, or conductor) the context they need without re-reading all your output.