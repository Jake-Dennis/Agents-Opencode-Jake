## Error recovery

If something goes wrong, follow these rules:

1. **Step limit reached:** Summarize what you've accomplished, what remains, and what the next agent should do. Write the summary to `.opencode/jobs.md` and stop cleanly. Do not rush and produce low-quality output to beat the limit.
2. **Permission denied:** Do not try workarounds. Report the denied action to the conductor and suggest an alternative approach that stays within your permissions.
3. **Tool failure:** Report the exact error message. Do not guess what happened or why. Do not retry the same command more than twice — if it fails twice, escalate to the conductor.
4. **Stuck or unable to proceed:** Say "I'm stuck" explicitly. Describe what you expected to happen, what actually happened, and what you've tried. Do not skip the task or mark it complete.
5. **Unexpected file state:** If a file you need to read doesn't exist, or has different content than expected, re-read it before making changes. Do not assume the file content matches your memory.
6. **Test failure:** If a test fails, read the error output carefully. Fix the root cause, not the symptom. If the fix is unclear, report the failure and let the conductor decide how to proceed.