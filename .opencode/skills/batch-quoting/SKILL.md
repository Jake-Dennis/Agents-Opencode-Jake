---
name: batch-quoting
description: Use when writing or editing a Windows `.bat` file, or when a value flows from `set VAR=...` into a parenthesized `( ... )` block. Covers `%VAR%` parse-time vs `!VAR!` delayed expansion, the `set "VAR=..."` quote-strip form, and the `::` label-inside-parens trap. Avoid for shell scripts, PowerShell, or any non-`.bat` context — this is Windows `.bat` only.
---

# Batch Quoting (`.bat` file gotchas)

This skill is the canonical reference for the 5-6 parser traps that bite every `.bat` file edit on this project. The patterns are: parse-time vs delayed expansion, the `set "VAR=..."` form, parens-block escaping, the `::` label-inside-parens trap, and the `%VAR%` empty-on-first-use trap.

## When to use

Any time the conductor or `@builder` writes or edits a `.bat` file in this project (e.g., `global-setup.bat`, `setup.bat`, `uninstall-global.bat`). Any time a value flows from one `set` line into a parenthesized `( ... )` block on a later line. Any time a `.bat` file errors with `cmd : : was unexpected at this time` or `cmd : . was unexpected at this time` or any `(%VAR% was unexpected at this time)`.

## Process / Checklist

### Rule 1: `%VAR%` is parse-time, `!VAR!` is delayed

`%VAR%` is expanded when the line is PARSED (before the line runs). `!VAR!` is expanded when the line RUNS. If you set a variable inside a `( ... )` block, `%VAR%` will be the empty string on the next line, but `!VAR!` will be the new value.

```bat
setlocal enabledelayedexpansion
set X=hello
(
    set X=world
    echo %X%  :: prints "hello" (parse-time)
    echo !X!  :: prints "world" (delayed)
)
```

**Trap:** if you forget `setlocal enabledelayedexpansion` at the top of the file, `!X!` is treated as a literal string (no expansion). The fix: add `setlocal enabledelayedexpansion` once at the top of the script (or inside the function that needs it).

### Rule 2: use `set "VAR=value"` to strip quotes and handle spaces

```bat
set "VAR=hello world"   :: VAR is set to "hello world" (quotes are stripped)
set VAR=hello world     :: SYNTAX ERROR — spaces break the parser
```

**Always use the `set "VAR=..."` form** when the value may contain spaces, parentheses, or `&`. The quotes are NOT part of the value; they tell the parser where the value starts and ends.

### Rule 3: parens-block escaping

Inside a `( ... )` block, every `(` and `)` must be balanced, and `(...)` blocks cannot span multiple lines without a `^` continuation. The bigger trap: comments using `::` or `(` inside a parens block are treated as labels or syntax.

```bat
(
    set X=1  :: this is fine
    :: :: this comment BREAKS — `::` inside parens is a label
    set Y=2
)
```

**Fix:** use `REM` instead of `::` inside parens blocks. `REM` is a real command; `::` is a label.

### Rule 4: `cmd : : was unexpected at this time` and `cmd : . was unexpected at this time`

These errors mean a `::` comment (or a `:` label) appeared inside a parens block. The parser sees `:` and tries to treat the next token as a label name, then fails because the line is inside a `( ... )` block.

**Fix:** change every `:: comment` inside `( ... )` to `REM comment`.

### Rule 5: `%VAR%` empty on first use inside parens

```bat
(
    set MERGE_ARGS=--unattended
    call python helper.py %MERGE_ARGS%  :: BUG: %MERGE_ARGS% is empty here
)
```

The `set MERGE_ARGS=...` line is inside the parens block, so `MERGE_ARGS` doesn't exist until runtime. But `%MERGE_ARGS%` is expanded at parse time (before the block runs), so it's empty.

**Fix:** use `!MERGE_ARGS!` (delayed) inside the block, or hoist the `set` out of the block. Always hoist when possible — delayed expansion has its own surprises.

### Rule 6: junction safety check via `findstr /C:` is unreliable

If you find yourself writing `findstr /C:"substr" output.txt` inside a parens block with `2^>nul` redirection, STOP. The `^` escape is consumed differently in `cmd /c` context vs. interactive shells, and the parens block confuses the parser.

**Fix:** simplify the check. Use `if not exist` (file or directory) and `if errorlevel 1` instead of `findstr` inside parens.

## Examples

### Example 1: `%REFRESH_ARGS%` parse-time bug (plan-004)

```bat
:: BEFORE (broken)
(
    set REFRESH_ARGS=--unattended
    call python graphify_refresh.py %REFRESH_ARGS%
)

:: AFTER (fixed)
setlocal enabledelayedexpansion
(
    set REFRESH_ARGS=--unattended
    call python graphify_refresh.py !REFRESH_ARGS!
)
```

Source: plan-004 work-log entry "Bug found during dev: %REFRESH_ARGS% (parse-time expansion) was empty at the .bat call site".

### Example 2: `::` comment inside parens (plan-002 follow-up)

```bat
:: BEFORE (broken — `:: comment` inside parens)
(
    set "GLOBAL_CONFIG=%USERPROFILE%\.config\opencode\opencode.jsonc"
    :: Junction safety check
    if not exist "%GLOBAL_CONFIG%" goto :no_config
    set "MANIFEST=%GLOBAL_CONFIG%\.opencode-jake-installed.json"
    :: Continue with install
    call :do_install
)

:: AFTER (fixed — REM instead of ::)
(
    set "GLOBAL_CONFIG=%USERPROFILE%\.config\opencode\opencode.jsonc"
    REM Junction safety check
    if not exist "%GLOBAL_CONFIG%" goto :no_config
    set "MANIFEST=%GLOBAL_CONFIG%\.opencode-jake-installed.json"
    REM Continue with install
    call :do_install
)
```

Source: plan-002 follow-up work-log entry "5 `::` comments inside parens blocks all fixed by converting to `REM`".

### Example 3: `set /p` with `(y/N)` in prompt (plan-002)

```bat
:: BEFORE (broken — unescaped parens confuse the parser)
set /p CONFIRM=Are you sure? (y/N):
if /i "!CONFIRM!"=="y" goto :do_install

:: AFTER (fixed — quotes around the whole prompt)
set /p "CONFIRM=Are you sure? (y/N): "
if /i "!CONFIRM!"=="y" goto :do_install
```

Source: plan-002 work-log entry "`set /p` with `(y/N)` in prompt — unescaped parens confused batch parser inside an `if (...) else (...)` block".

## Common pitfalls

- **Pitfall 1: "It works in my terminal"** — the test cycle is: run the `.bat` from `cmd /c` in the repo root. Don't test in an interactive `cmd` window; the bug-class doesn't show up there.
- **Pitfall 2: Forgetting `setlocal enabledelayedexpansion`** — without it, `!VAR!` is literal. Add it once at the top of the script, or at the top of the function that uses delayed expansion.
- **Pitfall 3: Using `::` comments inside `( ... )` blocks** — always `REM` inside parens.
- **Pitfall 4: Hoisting vs delayed expansion** — when in doubt, hoist the `set VAR=...` to BEFORE the `( ... )` block. Delayed expansion (`!VAR!`) is a tool of last resort.

## Reference: the 6 rules in one table

| Trap | Symptom | Fix |
|---|---|---|
| `%VAR%` parse-time | empty value when used inside `( ... )` | `!VAR!` + `setlocal enabledelayedexpansion` |
| `set VAR=val with spaces` | syntax error | `set "VAR=val with spaces"` |
| `::` inside parens | `cmd : : was unexpected at this time` | `REM` |
| `(y/N)` in `set /p` prompt | parser error | `set /p "VAR=prompt (y/N): "` |
| `findstr /C:` inside parens | unreliable `2^>nul` handling | use `if not exist` instead |
| `::` comment in `if (...)` block | parser error | `REM` |
