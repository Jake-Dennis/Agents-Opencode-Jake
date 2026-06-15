#!/usr/bin/env python3
"""Resolve {file:...} includes in .md files, inlining the referenced content.

Usage:
    python resolve_includes.py <source_dir> <output_dir> [--repo-root <path>]

Reads every .md file in <source_dir>, finds all ``{file:<path>}`` references,
reads the referenced file (relative to --repo-root, defaulting to source_dir's
parent's parent), and replaces the reference with the file's content.
Writes the resolved files to <output_dir>.

This is used by global-setup.bat to produce self-contained agent prompts
that don't depend on {file:} resolution at runtime.
"""

import argparse
import re
import sys
from pathlib import Path


FILE_REF = re.compile(r"\{file:([^}]+)\}")


def resolve_includes(src_dir: Path, out_dir: Path, repo_root: Path) -> int:
    """Resolve all {file:...} includes in .md files.

    Returns the number of files processed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for f in sorted(src_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        resolved = resolve_text(text, repo_root)

        out_file = out_dir / f.name
        out_file.write_text(resolved, encoding="utf-8")
        count += 1

        # Show what was resolved
        refs = FILE_REF.findall(text)
        if refs:
            print(f"  {f.name}: resolved {len(refs)} include(s)")
        else:
            print(f"  {f.name}: no includes to resolve")

    return count


def resolve_text(text: str, repo_root: Path) -> str:
    """Replace all {file:<path>} references with the file's content."""
    def _replace(m: re.Match) -> str:
        rel_path = m.group(1)
        target = repo_root / rel_path

        if not target.exists():
            print(f"  [WARN] include not found: {rel_path} (looked at {target})",
                  file=sys.stderr)
            return m.group(0)  # leave the reference as-is

        content = target.read_text(encoding="utf-8")
        # Recursively resolve includes in the included file
        return resolve_text(content, repo_root)

    return FILE_REF.sub(_replace, text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve {file:...} includes in .md files"
    )
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing source .md files with {file:} references",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory to write resolved .md files",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for resolving relative paths (default: source_dir/../../..)",
    )
    args = parser.parse_args()

    src_dir = args.source_dir.resolve()
    out_dir = args.output_dir.resolve()
    repo_root = (
        args.repo_root.resolve()
        if args.repo_root
        else (src_dir / ".." / "..").resolve()
    )

    if not src_dir.is_dir():
        print(f"[ERROR] source directory not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    count = resolve_includes(src_dir, out_dir, repo_root)
    print(f"Resolved includes in {count} files -> {out_dir}")


if __name__ == "__main__":
    main()