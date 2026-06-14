#!/usr/bin/env python3
"""Invoke each agent via opencode CLI and verify it responds."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Workaround for opencode bug #24204/#24747: OPENCODE_SERVER_PASSWORD env var
# inherited from desktop causes "Session not found" errors.
for _k in ("OPENCODE_SERVER_PASSWORD", "OPENCODE_SERVER_USERNAME"):
    os.environ.pop(_k, None)

PROJECT = Path(__file__).resolve().parent.parent
AGENTS = [
    "conductor", "planner", "builder", "architect", "reviewer",
    "tester", "docs", "debugger", "refactor", "git",
    "explorer", "security", "perf",
]
PROMPT = "Reply with exactly one short line: agent name and one phrase describing your role. No tool calls."
TIMEOUT_S = 90


def main():
    results = []
    print(f"Testing {len(AGENTS)} agents via opencode CLI (timeout {TIMEOUT_S}s each)")
    print(f"Project: {PROJECT}")
    print(f"Prompt: {PROMPT!r}")
    print("=" * 70)
    
    for agent in AGENTS:
        print(f"\n[{agent}]", end=" ", flush=True)
        cmd = [
            "opencode", "run",
            "--pure",
            "--dir", str(PROJECT),
            "--agent", agent,
            "--format", "default",
            "--title", f"test-{agent}",
            PROMPT,
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                shell=True,
            )
            dt = time.time() - t0
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            rc = proc.returncode
            response_text = ""
            for line in out.splitlines():
                line = line.strip()
                if line and not line.startswith("[") and not line.startswith("█"):
                    response_text = line
            # ok = (rc == 0) AND response mentions the agent name (case-insensitive)
            ok = (rc == 0) and bool(response_text) and agent in response_text.lower()
            results.append({
                "agent": agent,
                "ok": ok,
                "rc": rc,
                "elapsed": round(dt, 1),
                "response": response_text[:200] if response_text else "(no response)",
                "err_tail": err[-200:] if err else "",
            })
            print(f"rc={rc} {dt:.1f}s ok={ok}")
            if response_text:
                print(f"  > {response_text[:160]}")
            if err and rc != 0:
                print(f"  ! {err[-160:]}")
        except subprocess.TimeoutExpired:
            dt = time.time() - t0
            results.append({"agent": agent, "ok": False, "rc": -1, "elapsed": round(dt, 1), "response": "(timeout)", "err_tail": ""})
            print(f"TIMEOUT after {dt:.1f}s")
        except Exception as e:
            results.append({"agent": agent, "ok": False, "rc": -1, "elapsed": 0, "response": f"(error: {e})", "err_tail": ""})
            print(f"ERROR: {e}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"  {mark}  {r['agent']:12s}  rc={r['rc']:>3}  {r['elapsed']:>5.1f}s  {r['response'][:100]}")
    print(f"\nPASSED: {passed}/{len(results)}")
    print(f"FAILED: {failed}/{len(results)}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
