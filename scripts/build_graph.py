#!/usr/bin/env python3
"""Build knowledge graph for a project directory.

Usage: python build_graph.py <project_dir>
"""
import sys
import subprocess

def main():
    if len(sys.argv) < 2:
        print("Usage: python build_graph.py <project_dir>", file=sys.stderr)
        return 1
    target = sys.argv[1]
    if target.endswith("\\"):
        target = target[:-1]
    result = subprocess.run(
        [sys.executable, "-m", "graphify", target, "--depth", "5", "--export", "html", "--export", "json"],
        capture_output=True,
        text=True,
    )
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
