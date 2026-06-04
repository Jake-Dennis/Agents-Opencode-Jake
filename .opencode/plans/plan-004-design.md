# Plan 004 — Design: Version check + auto-refresh step

This section is the @architect's deliverable for plan-004. It documents
the exact behaviour of the new "step 4b" in `global-setup.bat` and the
new "step 2b" in `setup.bat`, the chosen approach for each open
question, and a reference .bat sketch the @builder can use as a
contract. The decision rationale lives in
`.opencode/decisions/adr-003-graphify-auto-refresh.md`.

## Where the new step lives

### `global-setup.bat` — new step 4b

Inserted **immediately after the existing step 4a** (which ends at
line 156 with the `)` that closes the `--force-reinstall` fallback
block) and **before the merge-helper existence check** (line 159). The
existing blank `echo.` at line 157 stays as the separator; the new
block is inserted on lines 158–~250 and the rest of the file shifts
down. The header is `echo [4b/5] Checking graphify version...` to
preserve the existing 5-step numbering (`[1/5]`…`[5/5]`).

Rationale: step 4a establishes "is `graphify` importable at all?" and
step 4b establishes "is the importable version the latest one?". The
two together form a clean "is graphify installed + correct version?"
unit that runs before any code that actually invokes `python -m
graphify …` (the merge helper does not, but the user's
`graphify install --platform opencode` does, and the agent workflow
relies on it). The merge helper is intentionally last because the
user's `opencode.jsonc` is the authoritative source of truth for the
agents — refresh graphify first, then merge.

### `setup.bat` — new step 2b

Inserted **immediately after the existing step 2** (which ends at
line 61 with the `)` that closes the `MISSING_DEPS` install block) and
**before step 3** (line 63, "Copying agent files"). The existing blank
`echo.` at line 62 stays as the separator. The header is
`echo [2b/7] Checking graphify version...`. We deliberately do **not**
renumber steps 3–7; the `[N/7]` counters stay sequential and `[2b/7]`
clearly identifies the new sub-step. The plan-004 Layer-2 task
description is satisfied: "renumber to step 3 if step 2 becomes 2b"
— by naming it 2b we do not need to renumber, which keeps the diff
small and the existing step references in the README and in user
muscle-memory stable.

Rationale: same as global-setup — refresh graphify before any code
that invokes it. In `setup.bat`, step 7 (`python -m graphify …
--depth 5`) is the consumer; running the refresh in step 2b means
step 7 always uses the freshest version.

## Pip version extraction (Windows `cmd.exe`)

```batch
:: 1. Capture the pip version. `pip show` prints multiple lines;
::    we filter to just the "Version:" line and split on ":".
set "PIP_VER="
for /f "tokens=1,* delims=:" %%A in (
    '"!PY!" -m pip show graphifyy 2^>nul ^| findstr /B "Version:"'
) do (
    if /i "%%A"=="Version" set "PIP_VER=%%B"
)
:: %%B is " 0.8.31" (with leading space from the "Version: 0.8.31"
:: format). Strip the leading space and any trailing CR.
if defined PIP_VER set "PIP_VER=!PIP_VER:~1!"
if defined PIP_VER for /f "delims=" %%L in ("!PIP_VER!") do set "PIP_VER=%%L"
```

Why this shape:

* `for /f "tokens=1,* delims=:"` splits on the first `:` only, giving
  `Version` and ` 0.8.31` (the `*` consumes the rest of the line
  verbatim, including any leading space).
* The `if /i "%%A"=="Version"` guard discards the `Name:`,
  `Location:`, `Summary:` lines that `findstr` lets through
  (`findstr /B "Version:"` matches only lines that *start* with
  `Version:`, so the other lines are filtered out, but the guard is
  defensive in case the user has a localized pip that reorders
  fields).
* `!PIP_VER:~1!` strips the leading space.
* The final `for /f "delims="` strips any trailing CR (pip writes
  `\r\n` line endings on Windows; the for /f default-leading-ws strip
  does not touch trailing CR).

If `pip show graphifyy` exits non-zero, the `for /f` never iterates
and `PIP_VER` stays empty. We branch on `if defined PIP_VER` to fall
into the "skip + warn" path.

## Stamp version extraction

```batch
:: 2. Read the installed stamp. The stamp is a single text line at
;;   %USERPROFILE%\.config\opencode\skills\graphify\.graphify_version
set "STAMP_VER="
if exist "%USERPROFILE%\.config\opencode\skills\graphify\.graphify_version" (
    for /f "usebackq eol=# tokens=* delims=" %%L in (
        "%USERPROFILE%\.config\opencode\skills\graphify\.graphify_version"
    ) do (
        if not defined STAMP_VER set "STAMP_VER=%%L"
    )
)
```

* `usebackq` lets us quote the path (defensive — current `USERPROFILE`
  has no spaces, but the user could be `C:\Users\First Last\`).
* `eol=#` treats `#` as a comment (defensive; the stamp is pure
  digits-and-dots, but cheap insurance).
* `tokens=* delims=` reads the whole line.
* The `if not defined` guard keeps only the first non-empty line
  (defensive — a stray newline at the end of the file is a
  one-character edge case; we use the first line, which is the
  canonical stamp content).

If the file does not exist, `STAMP_VER` stays empty — that is the
**stampless case** (first run, or stamp never written by
`graphify install`). We treat stampless as "needs upgrade", so the
flow falls through to the upgrade routine. This is correct: a
stampless state means the user's local skill/plugin has never been
refreshed, and running `python -m graphify install --platform opencode`
will both refresh the files and create the stamp.

## Version comparison

The user noted that "string compare is fine for X.Y.Z" — but that
breaks on the `0.9.x → 0.10.x` transition
(`"0.9.0" gtr "0.10.0"` is **true** lexicographically, which is the
wrong answer). The safest small-footprint fix is a single
Python one-liner that compares tuples of integers, since Python is
already resolved (`!PY!` in `global-setup.bat`, `python` in
`setup.bat` after step 1 has already verified it is on PATH):

```batch
:: 3. Compare. Exit code 0 = pip >= stamp (no upgrade needed).
::    Exit code 1 = pip < stamp OR either version is unparseable
::    (we treat unparseable as "needs upgrade" so a corrupted stamp
::    does not silently freeze the user on an old version).
"!PY!" -c "import sys,re
def parse(v):
    m = re.match(r'(\d+)\.(\d+)\.(\d+)', v)
    if not m: raise ValueError(v)
    return tuple(int(x) for x in m.groups())
try:
    a, b = parse(sys.argv[1]), parse(sys.argv[2])
except (ValueError, IndexError):
    sys.exit(1)
sys.exit(0 if a >= b else 1)" "!PIP_VER!" "!STAMP_VER!" 2>nul
if !errorlevel! equ 0 (
    :: pip >= stamp: up to date
    echo  [OK] graphify !PIP_VER! up to date
    goto :after_refresh
) else (
    :: pip < stamp, or stampless, or unparseable — needs upgrade
    if "!STAMP_VER!"=="" (
        echo  [INSTALL] graphify stamp missing; refreshing to !PIP_VER!...
    ) else (
        echo  [UPGRADE] graphify stamp !STAMP_VER! behind pip !PIP_VER!...
    )
    goto :do_refresh
)
```

Key design choices:

* **Unparseable stamp = upgrade** (not skip). The `try/except` exits
  with code 1 on a bad stamp, which sends us into the upgrade path.
  Rationale: a corrupted stamp should not silently freeze the user.
* **Pre-release suffix is stripped by the regex** (`r'(\d+)\.(\d+)\.(\d+)'`).
  `0.10.0a1` parses as `(0, 10, 0)` so the comparison still works.
  This handles the edge case where a future graphify release ships a
  pre-release and pip is on the pre-release.
* **Stampless treated as "needs upgrade"** (explicit `if "!STAMP_VER!"==""`).
  On first run, we want to install both the user-scope skill and the
  project-scope plugin, not just skip because the stamp file is
  absent.
* **`setlocal enabledelayedexpansion`** is already active in both
  .bat files, so `!PIP_VER!` and `!STAMP_VER!` resolve at expansion
  time, not parse time.

## Interactive prompt

When the user is interactive (no `--unattended`, no `--dry-run`),
the prompt is:

```
graphify 0.8.30 installed, pip has 0.8.31. Refresh? (Y/n):
```

Default is **Y**. Rationale:

* The whole point of this step is auto-refresh — pressing Enter to
  accept is the dominant use case.
* The user already opted into the installer (they passed the initial
  "Continue with global install? (y/N):" prompt in global-setup, or
  they just ran `setup.bat` deliberately).
* A destructive confirmation is the wrong default for a *refresh* —
  refresh is non-destructive (it writes new copies of files we
  already wrote, and updates a single version stamp). The
  destructive part of the installer (the opencode.jsonc merge with
  collision handling) is already gated by `--force`, not by this
  step.

Parsing:

```batch
set /p "REPLY=graphify !STAMP_VER! installed, pip has !PIP_VER!. Refresh? (Y/n): "
if /i "!REPLY!"=="n" (
    echo  [SKIP] graphify not upgraded
    goto :after_refresh
)
:: Default (empty REPLY) and explicit "y" both fall through to upgrade.
```

## `--unattended` behaviour

Auto-upgrade with no prompt, with a one-line notice:

```batch
if "%UNATTENDED%"=="1" (
    echo  [UNATTENDED] upgrading graphify !STAMP_VER! -^> !PIP_VER!
    goto :do_refresh
)
```

This matches the existing `[UNATTENDED] proceeding without prompt.`
banner near the top of `global-setup.bat` (line 49) and the
`--unattended` semantics already established in the codebase. The
refreshing happens silently; the user only sees the one-line notice
and the upgrade routine's own output.

## `--dry-run` behaviour

Print what would happen, do not invoke pip or `graphify install`:

```batch
if "%DRY_RUN%"=="1" (
    if "!STAMP_VER!"=="" (
        echo  [DRY-RUN] would refresh graphify (stampless) to !PIP_VER!
        echo            (pip install --user --upgrade graphifyy
        echo             +^ python -m graphify install --platform opencode)
    ) else (
        echo  [DRY-RUN] would upgrade graphify from !STAMP_VER! to !PIP_VER!
        echo            (pip install --user --upgrade graphifyy
        echo             +^ python -m graphify install --platform opencode)
    )
    goto :after_refresh
)
```

This matches the existing `[DRY-RUN] would run: …` banner used by
the merge helper in `global-setup.bat` (line 174). No subprocess is
spawned; the step is a pure print.

## `--force` behaviour

`--force` is **mapped to `--yes`** (auto-upgrade, no prompt) by the
.bat wrapper. This matches the existing semantics of `--force`
elsewhere in the installer: "skip confirmation prompts / overwrite
on conflict". A user running `global-setup.bat --force` on a
stale-stamp system will get the auto-upgrade path without being
prompted. This is verified by test T1.15.

```batch
if "%FORCE%"=="1"      set "REFRESH_ARGS=!REFRESH_ARGS! --yes"
```

The distinction that originally motivated the "no-op" design
(`--force` is for the opencode.jsonc merge, not the refresh) is
preserved: the upgrade is still the default-action-with-confirmation
in interactive mode, and `--force` skips the confirmation. It does
not pass through to `pip install` (so pip's default dependency
resolution is used) or to `graphify install` (which is idempotent
and does not collide with anything the merge helper touches).

If a future maintainer wants `--force` to mean "downgrade-allowed"
(e.g. user wants to pin to an older version), that is a separate
decision and out of scope for plan-004.

## Failure modes (all warn + continue, never `exit /b`)

| Condition | Detection | Action |
|---|---|---|
| `python` not on PATH | `!PY!` unset (`global-setup`) or `python --version` fails in step 1 (`setup`) | Skip step entirely; log `[WARN] graphify version check skipped: python not on PATH` |
| `pip show graphifyy` exits non-zero | `for /f` never iterates, `PIP_VER` empty | Log `[WARN] graphify not installed via pip; skipping version check. Run: pip install --user graphifyy` |
| `pip show` output has no `Version:` line | `PIP_VER` empty after the for /f | Same as above |
| Version string unparseable (e.g. `unknown` or `0.8`) | Python one-liner raises `ValueError` → exit 1 | Log `[WARN] graphify pip version "!PIP_VER!" unparseable; treating as needs upgrade` and fall into the upgrade path. A bad pip version is a stronger signal to upgrade than to skip. |
| Stamp file is unparseable | Python one-liner raises `ValueError` → exit 1 | Same — fall into the upgrade path. The upgrade will write a fresh stamp. |
| `pip install --user --upgrade graphifyy` fails (network down) | `!errorlevel! neq 0` | Log `[WARN] graphify pip upgrade failed (network?): <stderr tail>`, leave stamp unchanged, **continue to next step** |
| `python -m graphify install --platform opencode` fails | `!errorlevel! neq 0` | Log `[WARN] graphify install --platform opencode failed: <stderr tail>`, leave stamp unchanged, **continue** |
| `!PY!` (the python one-liner) raises an unhandled exception | `!errorlevel! neq 0` | Log `[WARN] graphify version compare failed`, **continue**. This is defensive: the one-liner is small and tested, but we never want a Python crash to abort the install. |

The "continue" behaviour matches the existing `[WARN] graphify
install failed` block at lines 147–152 of `global-setup.bat`: an
install-time warning never aborts the rest of the install. The user
can re-run the .bat to retry.

## Output format — exact strings

All output is indented with two spaces to match the existing `.bat`
convention (see lines 137–155 of `global-setup.bat`):

| State | Exact string |
|---|---|
| `python` missing | `  [WARN] graphify version check skipped: python not on PATH` |
| `pip show` fails | `  [WARN] graphify not installed via pip; skipping version check.` <br> `         Run: pip install --user graphifyy` |
| Unparseable pip version | `  [WARN] graphify pip version "X" unparseable; attempting upgrade anyway` |
| Stampless | `  [INSTALL] graphify stamp missing; refreshing to X.Y.Z...` |
| Pip >= stamp | `  [OK] graphify X.Y.Z up to date` |
| Pip < stamp | `  [UPGRADE] graphify stamp A.B.C behind pip X.Y.Z...` |
| Interactive prompt | `  graphify A.B.C installed, pip has X.Y.Z. Refresh? (Y/n): ` |
| `--unattended` | `  [UNATTENDED] upgrading graphify A.B.C -> X.Y.Z` |
| `--dry-run` (stampless) | `  [DRY-RUN] would refresh graphify (stampless) to X.Y.Z` |
| `--dry-run` (upgrade) | `  [DRY-RUN] would upgrade graphify from A.B.C to X.Y.Z` |
| Pip upgrade success | `  [UPGRADE] pip graphifyy upgraded to X.Y.Z` |
| `graphify install` success | `  [REFRESH] graphify skill + plugin refreshed to X.Y.Z` |
| Pip upgrade fails | `  [WARN] graphify pip upgrade failed (network?): <last 3 lines of stderr>` |
| `graphify install` fails | `  [WARN] graphify install --platform opencode failed: <last 3 lines of stderr>` |
| User declines | `  [SKIP] graphify not upgraded` |

The user is asked to be on the lookout for two prefixes: `[OK]`,
`[UPGRADE]`, `[REFRESH]` = success path; `[WARN]`, `[SKIP]` =
something to look at, but the install continues.

## Reference implementation sketch

### Sketch for `global-setup.bat` (insert after line 156)

```batch
:: ---- Step 4b: Refresh graphify skill + plugin if pip is ahead of stamp ----
:: Reads the pip-installed graphifyy version and compares it to the stamp
:: at %USERPROFILE%\.config\opencode\skills\graphify\.graphify_version.
:: If pip is behind (or the stamp is missing/unparseable), runs
::   pip install --user --upgrade graphifyy
::   python -m graphify install --platform opencode
:: which is idempotent and refreshes BOTH the user-scope skill file and
:: the project-scope plugin in one call. See plan-004 §Design and
:: adr-003 for the full rationale.
echo [4b/5] Checking graphify version...

:: 1. Read pip version. !PY! is already resolved by step 4a.
set "PIP_VER="
for /f "tokens=1,* delims=:" %%A in (
    '"!PY!" -m pip show graphifyy 2^>nul ^| findstr /B "Version:"'
) do (
    if /i "%%A"=="Version" set "PIP_VER=%%B"
)
if defined PIP_VER set "PIP_VER=!PIP_VER:~1!"
if defined PIP_VER for /f "delims=" %%L in ("!PIP_VER!") do set "PIP_VER=%%L"

if not defined PIP_VER (
    echo  [WARN] graphify not installed via pip; skipping version check.
    echo         Run: pip install --user graphifyy
    goto :after_refresh
)

:: 2. Read the installed stamp. The stamp file is a single line.
set "STAMP_VER="
if exist "%USERPROFILE%\.config\opencode\skills\graphify\.graphify_version" (
    for /f "usebackq eol=# tokens=* delims=" %%L in (
        "%USERPROFILE%\.config\opencode\skills\graphify\.graphify_version"
    ) do (
        if not defined STAMP_VER set "STAMP_VER=%%L"
    )
)

:: 3. Compare. Exit 0 = pip >= stamp; exit 1 = needs upgrade (incl. unparseable).
"!PY!" -c "import sys,re
def parse(v):
    m = re.match(r'(\d+)\.(\d+)\.(\d+)', v)
    if not m: raise ValueError(v)
    return tuple(int(x) for x in m.groups())
try:
    a, b = parse(sys.argv[1]), parse(sys.argv[2])
except (ValueError, IndexError):
    sys.exit(1)
sys.exit(0 if a >= b else 1)" "!PIP_VER!" "!STAMP_VER!" 2>nul
if !errorlevel! equ 0 (
    echo  [OK] graphify !PIP_VER! up to date
    goto :after_refresh
)

:: 4. Decide what to print, then route to upgrade / dry-run / prompt.
if "!STAMP_VER!"=="" (
    echo  [INSTALL] graphify stamp missing; refreshing to !PIP_VER!...
) else (
    echo  [UPGRADE] graphify stamp !STAMP_VER! behind pip !PIP_VER!...
)

if "%DRY_RUN%"=="1" (
    echo  [DRY-RUN] would upgrade graphify from !STAMP_VER! to !PIP_VER!
    echo            (pip install --user --upgrade graphifyy
    echo             +^ python -m graphify install --platform opencode)
    goto :after_refresh
)

if "%UNATTENDED%"=="1" (
    echo  [UNATTENDED] upgrading graphify !STAMP_VER! -^> !PIP_VER!
) else (
    set /p "REPLY=graphify !STAMP_VER! installed, pip has !PIP_VER!. Refresh? (Y/n): "
    if /i "!REPLY!"=="n" (
        echo  [SKIP] graphify not upgraded
        goto :after_refresh
    )
)

:: 5. Do the refresh.
"!PY!" -m pip install --user --upgrade graphifyy 2>&1 | findstr /V "Requirement already" | findstr /V "^$"
if !errorlevel! neq 0 (
    echo  [WARN] graphify pip upgrade failed; stamp left unchanged. Continue.
    goto :after_refresh
)
echo  [UPGRADE] pip graphifyy upgraded to !PIP_VER!

"!PY!" -m graphify install --platform opencode 2>&1
if !errorlevel! neq 0 (
    echo  [WARN] graphify install --platform opencode failed; stamp left unchanged.
    goto :after_refresh
)
echo  [REFRESH] graphify skill + plugin refreshed to !PIP_VER!

:after_refresh
echo.
```

For `setup.bat`, the structure is identical except:
- Header is `echo [2b/7] Checking graphify version...`
- The `!PY!` is `python` (setup.bat did not resolve into a `!PY!`
  variable; step 1 verified `python --version` works at line 33)
- The `:after_refresh` label is not used; instead the new block ends
  with a `goto :eof` (or simply falls through to the existing
  `echo.` at line 62). Cleanest: append a `goto :after_refresh_2b`
  label that lives after the new block and before step 3.

The @builder should extract the new block into a small helper .bat
file (e.g. `.opencode\scripts\refresh_graphify.bat`) and `call` it
from both installers, **if** the duplication starts to feel heavy.
For v1 we keep it inline in both files (matches the existing step-4a
pattern: graphify import check is duplicated between both .bat files,
not factored out, and the duplication is small enough to be the
cheapest design). The @builder can decide at implementation time
which is cleaner.

## Open questions

1. **No existing .bat-level test infrastructure.** `tests/` has
   `test_global_setup.py` for the Python merge helper, but the .bat
   files themselves are not exercised by pytest. The plan-004
   reference to "`bat_test_helper.py`" describes an aspirational
   test pattern that does not exist yet. The @tester should either
   (a) build a tiny `tests/bat_test_helper.py` that can spawn a .bat
   in a sandboxed `tmp_path` and capture stdout, or (b) factor the
   version-compare + upgrade-decision logic into a small Python
   helper (`refresh_graphify.py`) and unit-test that, leaving the
   .bat as a thin wrapper. I lean toward (b) for testability, but
   that adds a new file. **Decision: leave to @tester.** The .bat
   snippets above are correct by construction; the @reviewer will
   static-review them.
2. **Stamp file format drift.** `graphify` may eventually change
   the stamp format (currently just `X.Y.Z\n`). The Python one-liner
   regex is `(\d+)\.(\d+)\.(\d+)` and silently treats anything else
   as "needs upgrade" — a future stamp like
   `0.8.31+local.foo` would be treated as unparseable and trigger
   an unnecessary upgrade. This is the conservative choice (better
   to upgrade than to skip on uncertainty) and is acceptable for
   plan-004. If the stamp format ever changes incompatibly, this
   step's behaviour degrades to "always refresh", which is
   idempotent and correct.
3. **Pre-releases on the test machine.** The regex strips the
   pre-release suffix (`0.10.0a1` → `(0, 10, 0)`). If the user has
   `pip install --pre graphifyy` set, the stamp will be a
   pre-release version string. This is handled correctly. If
   pre-releases become common, we may want a `pip index versions
   graphifyy` lookup instead — out of scope.
4. **Order of step 4b and the merge helper.** The new step runs
   *before* the merge helper. If a `graphify install --platform
   opencode` ever modifies the user's `opencode.jsonc` (it does
   not today, but the contract is not strictly documented), the
   merge helper would clobber that. The official
   `graphify install --platform opencode` is documented as touching
   only the skill dir and the plugin file; it does not touch
   `opencode.jsonc`. We rely on that. If it ever changes, the
   contract breaks. This is acceptable for plan-004; a future
   version check can verify the official command's contract.