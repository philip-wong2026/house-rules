# Windows compatibility checklist / Windows 兼容性清单

**Status / 状态: NOT VERIFIED ON WINDOWS. 待 GitHub 自动试装实测。**
The author has no Windows machine. Everything below is a code-level review on macOS plus a Python 3.9 run on macOS. "Compatible by design" is not "tested on Windows". The only real proof will be the `install-test` workflow (`.github/workflows/install-test.yml`, `windows-latest`, Python 3.9 and 3.12), which runs after the repository exists. 作者没有 Windows 电脑，下表只是在 macOS 上按代码审查得出的“设计上兼容”，不等于在 Windows 上通过。

| # | Item / 项目 | What the code does / 做法 | Where / 位置 | Windows result |
|---|---|---|---|---|
| 1 | Paths | `pathlib.Path` everywhere; relative paths written with `/` (`as_posix()`); no hard-coded `/` or drive letters; `os.path.normcase` when comparing | all tools, `setup.py` | 待 GitHub 自动试装实测 |
| 2 | Home folder | `Path.home()` for the temporary-allow file (`%USERPROFILE%\.space-open\...`) | `tools/hooks/pre_write_guard.py` | 待 GitHub 自动试装实测 |
| 3 | Line endings | every file written with `newline="\n"` (via `common.write_text` or `open(..., newline="\n")`); `.gitattributes` has `* text=auto eol=lf` so checkouts stay LF | `tools/common.py`, `tools/recycle.py`, `.gitattributes` | 待 GitHub 自动试装实测 |
| 4 | Text encoding | every read/write names `encoding="utf-8"`; stdout/stderr switched to UTF-8 with `reconfigure` so Chinese text does not hit the legacy code page; hook stdin read as bytes then decoded as UTF-8 | `common.stdio_utf8`, `common.read_stdin_text` | 待 GitHub 自动试装实测 |
| 5 | No shell-specific commands | no `shell=True`, no `os.system`, no `cp/mv/rm/cat/sed` calls; `subprocess` always gets an argument list and `sys.executable` | `setup.py`, `scripts/privacy_scan.py` (only `git`) | 待 GitHub 自动试装实测 |
| 6 | No POSIX-only modules | no `fcntl`, `pwd`, `os.getuid`, `chmod` bits, `zoneinfo`; file locks use `os.open(..., O_CREAT\|O_EXCL)` and `os.replace` | `tools/shared_write.py`, `tools/recycle.py` | 待 GitHub 自动试装实测 |
| 7 | Python version | Python 3.9 syntax (`from __future__ import annotations`, no `match`, no `X \| Y` at runtime). Tests were run on 3.9.6 and 3.14 on macOS and pass; this found and fixed one 3.10-only call (`Path.write_text(newline=)`) | all `.py` | 3.9 on macOS: passed. Windows: 待 GitHub 自动试装实测 |
| 8 | Command name | `setup.py` writes the interpreter given by `--python-command` or `sys.executable` into the hook command (quoted, forward slashes). Docs say use `python` instead of `python3` on Windows | `setup.py`, `INSTALL.md` | 待 GitHub 自动试装实测 |
| 9 | Symlinks | `recycle.py` refuses symlinks, so Windows without symlink rights is not a problem; tests that need symlinks skip when they cannot be created | `tools/recycle.py`, `tests/test_tools.py` | 待 GitHub 自动试装实测 |
| 10 | File names | no `:` or other reserved characters in names the tools create; backup stamps are `@HHMMSS` | `tools/backup.py` | 待 GitHub 自动试装实测 |
| 11 | Sync-conflict patterns | only scanned when `uses_sync_drive` is true; the names themselves are Windows-legal | `tools/common.py` | 待 GitHub 自动试装实测 |
| 12 | CI shell | workflow steps use `shell: bash` (Git Bash on `windows-latest`) with forward-slash relative paths, `$RUNNER_TEMP` and `find ... \| head -1` | `.github/workflows/install-test.yml` | 待 GitHub 自动试装实测 |

## Known limits that are not "verified" either way / 已知局限

- **Claude Code hooks on Windows are unverified.** The hook command is `"<python>" .space/hooks/<name>.py` with a relative script path, so Claude Code must be opened at the Space root. How Claude Code on Windows launches that command (shell, quoting, working directory) has not been tested by the author. `setup.py --check` only proves that the hook scripts behave when called with `sys.executable`.
- **The Bash check in the write guard parses POSIX shell syntax** (`shlex`). PowerShell and `cmd` command lines are not understood; on Windows the guard is reliable mainly for the file-edit tools (rules A1-A8), and only best-effort for shell commands (A9). It is a slip guard, not a security boundary, on every platform.
- **Long paths** (over 260 characters) and OneDrive "Files On-Demand" placeholders were not considered.
- **Antivirus or locked files**: `os.replace` can fail on Windows if another program holds the file open; the tools report the error and leave the original untouched.

## How this will be verified / 怎么验证

1. Create the GitHub repository (requires the author's approval; not done).
2. Push; the `install-test` workflow runs on `windows-latest` with Python 3.9 and 3.12: unit tests, English and Chinese non-interactive installs, `setup.py --check`, backup / recycle / restore round trip, privacy scan.
3. Only after that run is green may this file say "passed on Windows", and only for what the run actually covers (not Claude Code hooks, which need a person on Windows).
