# Plan 014-A: jobs.md Archival and Rotation — Design

## Goal

Design an archival/rotation mechanism for `.opencode/jobs.md` so it does not grow unbounded. Jobs entries accumulate over time; without a retention policy the file will grow large enough to degrade context window usage.

## Constraints

1. **Do not break live progress tracking.** The mechanism must not interfere with a running dispatch layer's ability to write new entries.
2. **Do not destroy history.** Old entries move to archive, not trash.
3. **No external dependencies.** Plain Python or bash, no npm/cargo/etc.
4. **Integrate into conductor's step 10 (DOCUMENT).** The conductor already appends to work-log.md and creates ADRs; archives can be part of that same step.

## Design

### Archive location

```
.opencode/jobs/
├── 2026-06-01.md
├── 2026-06-02.md
├── 2026-06-03.md
└── ...
```

One file per UTC date when archiving was triggered. The filename is the ISO date when the archive was created, not the date of the entries (since entries may span multiple days).

### Trigger

The conductor checks `jobs.md` size during **step 10 (DOCUMENT)** of the 14-step workflow. If the file exceeds a threshold (default: **20 KB**), the conductor:

1. Extracts all completed entries (Status: `complete`, `failed`, or `blocked` with no `in_progress` remaining)
2. Writes them to `.opencode/jobs/<YYYY-MM-DD>.md` as a single atomic write
3. Truncates `jobs.md` to only the in-progress entries (if any) plus a header comment noting the archive date

### Entry selection

Only entries whose **last status line is `complete`**, `failed`, or `blocked` are archived. Any entry whose Status is still `in_progress` stays in the live file. This ensures in-flight dispatches are not disrupted.

### The archived file format

```markdown
# Archived jobs — 2026-06-08

These entries were archived from .opencode/jobs.md on 2026-06-08.

## [plan-014] @builder - Add jobs.md archival
Status: complete
Started: 2026-06-08T10:00:00Z
Completed: 2026-06-08T10:15:00Z

- [x] Read jobs.md
- [x] Determine file size
- [x] Extract completed entries
- [x] Write archivefile
- [x] Truncate jobs.md
```

### Implementation options

**Option A: bash script** — `scripts/archive-jobs.sh`
- Uses `grep`/`sed`/`awk` to parse and split the file
- Fast, no Python dep
- Fragile with complex markdown

**Option B: Python script** — `scripts/archive-jobs.py`
- Uses regex or line-by-line parsing
- More maintainable, testable
- Preferred

**Option C: conductor prompt verbatim**
- The conductor reads jobs.md, splits entries manually, writes archive, truncates
- No script needed but error-prone and takes more tokens per dispatch

**Recommendation: Option B** — a Python script with tests.

### Conductor prompt addition (step 10)

In the conductor's step 10 (currently "Document — work-log, ADRs, project docs, graphify rationale"), append:

> **10a. Jobs archival** — If `.opencode/jobs.md` exceeds 20 KB, run `python scripts/archive-jobs.py` to archive completed entries. If the script is not available, skip.

### Edge cases

- **Empty jobs.md after truncation**: Leave the header + the completed split note. Do not delete the file.
- **Script missing**: Skip archival (log a warning in work-log).
- **Archive dir missing**: Script creates it.
- **Entry with no status**: Treated as `in_progress` (stays in live file).
- **Multiple dispatches in same second**: Timestamps are ISO-8601 with second granularity; same-second entries stay in order.
