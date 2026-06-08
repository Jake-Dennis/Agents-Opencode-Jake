#!/usr/bin/env python3
"""archive-jobs.py — Archive completed entries from .opencode/jobs.md.

Usage:
    python scripts/archive-jobs.py [--force] [--max-size KB]

Reads .opencode/jobs.md, extracts completed entries (Status: complete|failed|blocked),
writes them to .opencode/jobs/<YYYY-MM-DD>.md, and truncates the live file to
only in-progress entries.

Designed to be run by the conductor during step 10 (DOCUMENT) when jobs.md
exceeds a size threshold (default: 20 KB).
"""

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_FILE = REPO_ROOT / ".opencode" / "jobs.md"
ARCHIVE_DIR = REPO_ROOT / ".opencode" / "jobs"
DEFAULT_MAX_SIZE_KB = 20


def parse_jobs(text: str) -> list[dict]:
    """Parse jobs.md into entries.

    Each entry starts with a ## [<plan-id>] @<agent> header and contains
    key: value metadata lines followed by a task list.
    Returns list of dicts with keys: header, status, started, completed,
    steps, raw (the full entry text).
    """
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("## ["):
            # Save previous entry
            if current is not None:
                entries.append(current)
            current = {"header": line, "lines": [line], "status": "unknown"}
        elif current is not None:
            current["lines"].append(line)
            lower = line.lower()
            if lower.startswith("status:"):
                current["status"] = line.split(":", 1)[1].strip()
    # Don't forget the last entry
    if current is not None:
        entries.append(current)
    return entries


def is_complete(entry: dict) -> bool:
    """An entry is complete if its Status is 'complete', 'failed', or 'blocked'."""
    return entry.get("status", "").lower() in ("complete", "failed", "blocked")


def run(max_size_kb: int, force: bool = False) -> int:
    if not JOBS_FILE.exists():
        print(f"jobs.md not found at {JOBS_FILE}")
        return 0  # Not an error — file may not exist yet

    size_bytes = JOBS_FILE.stat().st_size
    size_kb = size_bytes / 1024

    if not force and size_kb < max_size_kb:
        print(f"jobs.md is {size_kb:.1f} KB (threshold: {max_size_kb} KB) — no archival needed")
        return 0

    text = JOBS_FILE.read_text(encoding="utf-8")
    entries = parse_jobs(text)

    if not entries:
        print("No entries found in jobs.md")
        return 0

    completed = [e for e in entries if is_complete(e)]
    in_progress = [e for e in entries if not is_complete(e)]

    if not completed:
        print(f"All {len(entries)} entries are in-progress — no archival needed")
        return 0

    # Create archive directory
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Write archive file
    today = date.today().isoformat()
    archive_path = ARCHIVE_DIR / f"{today}.md"
    archive_lines = [
        f"# Archived jobs — {today}",
        "",
        f"These entries were archived from {JOBS_FILE.name} on {today}.",
        f"Source size before archival: {size_kb:.1f} KB",
        f"Entries archived: {len(completed)}",
        f"Entries remaining: {len(in_progress)}",
        "",
    ]
    for entry in completed:
        archive_lines.append("")
        archive_lines.extend(entry.get("lines", []))

    archive_path.write_text("\n".join(archive_lines) + "\n", encoding="utf-8")
    print(f"Archived {len(completed)} completed entries to {archive_path}")

    # Truncate jobs.md to only in-progress entries
    if in_progress:
        new_lines = [
            "# jobs.md — Live Progress Tracking",
            "",
            "> This file is auto-managed by subagents. Do not edit by hand.",
            f"> Entries before {today} have been archived to {ARCHIVE_DIR.name}/",
            "",
        ]
        for entry in in_progress:
            new_lines.append("")
            new_lines.extend(entry.get("lines", []))
        JOBS_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"Truncated jobs.md to {len(in_progress)} in-progress entries ({len(new_lines)} lines)")
    else:
        # All entries were completed — reset to header only
        JOBS_FILE.write_text(
            f"# jobs.md — Live Progress Tracking\n\n"
            f"> All entries before {today} have been archived.\n"
            f"> File reset to empty state.\n",
            encoding="utf-8",
        )
        print("All entries archived — jobs.md reset to header-only")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Archive completed entries from .opencode/jobs.md"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force archival even if under size threshold"
    )
    parser.add_argument(
        "--max-size", type=int, default=DEFAULT_MAX_SIZE_KB,
        help=f"Size threshold in KB (default: {DEFAULT_MAX_SIZE_KB})"
    )
    args = parser.parse_args()
    sys.exit(run(max_size_kb=args.max_size, force=args.force))


if __name__ == "__main__":
    main()
