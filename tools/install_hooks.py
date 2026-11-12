#!/usr/bin/env python3
"""Register the HouseRules hooks for Claude Code, at the Space root AND in every top-level folder.

Why every folder: Claude Code reads .claude/settings.json from the folder it is opened in. A session
opened in "work/" does not see the root settings, so without this the write guard silently does not
run there. Every hook command uses absolute paths (python and script), so it works from any folder.

Run it again (python3 .space/install_hooks.py) after you add a new top-level folder, move the Space,
or upgrade Python: it refreshes every entry in place. Existing settings are merged, never replaced,
and a backup is taken before each change. Folders deeper than one level are not covered: open
Claude Code at the Space root or in a top-level folder. Standard library only; Python 3.9+.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backup as backup_mod  # noqa: E402
import common  # noqa: E402

HOOK_FILES = ("pre_write_guard.py", "turn_check.py")
SKIP = {".space", ".claude", ".git", "templates", "tools", "node_modules", "__pycache__"}


def _q(s):
    return '"' + s.replace("\\", "/") + '"'


def hook_commands(root, python_cmd=None):
    py = python_cmd or sys.executable
    hooks = Path(root).resolve() / ".space" / "hooks"
    return {name: f"{_q(py)} {_q(str(hooks / name))}" for name in HOOK_FILES}


def folders(root):
    root = Path(root).resolve()
    out = [root]
    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if p.is_dir() and not p.is_symlink() and not p.name.startswith(".") and p.name not in SKIP:
            out.append(p)
    return out


def _wanted(cmds):
    return {
        "PreToolUse": ({"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash"}, cmds["pre_write_guard.py"]),
        "SessionStart": ({}, cmds["turn_check.py"]),
        "UserPromptSubmit": ({}, cmds["turn_check.py"]),
    }


def merge(path, root, cmds):
    """Merge our hooks into one settings file. Returns 'created' | 'merged' | 'unchanged' | 'bad_json'."""
    data, existed = {}, path.exists()
    if existed:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (ValueError, OSError):
            return "bad_json"
    before = json.dumps(data, sort_keys=True)
    hooks = data.setdefault("hooks", {})
    for event, (extra, command) in _wanted(cmds).items():
        groups = hooks.setdefault(event, [])
        script = command.rsplit("/", 1)[-1].strip('"')
        found = False
        for g in groups:
            for h in g.get("hooks", []):
                if script in h.get("command", ""):
                    found = True
                    h["command"] = command  # refresh old relative or stale absolute paths
        if not found:
            groups.append({**extra, "hooks": [{"type": "command", "command": command}]})
    if json.dumps(data, sort_keys=True) == before:
        return "unchanged"
    if existed:
        backup_mod.backup(path, root, common.now_local())
    common.write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return "merged" if existed else "created"


def install(root, python_cmd=None):
    root = Path(root).resolve()
    cmds = hook_commands(root, python_cmd)
    report = []
    for folder in folders(root):
        path = folder / ".claude" / "settings.json"
        report.append({"file": path.relative_to(root).as_posix(), "result": merge(path, root, cmds)})
    return report


def missing(root):
    """Folders (relative, '.' = root) whose settings lack a working absolute hook command."""
    root = Path(root).resolve()
    bad = []
    for folder in folders(root):
        rel = "." if folder == root else folder.relative_to(root).as_posix()
        path = folder / ".claude" / "settings.json"
        try:
            blob = json.dumps(json.loads(path.read_text(encoding="utf-8")).get("hooks", {}), ensure_ascii=False)
        except (OSError, ValueError, AttributeError):
            bad.append(rel)
            continue
        want = [str(root / ".space" / "hooks" / n).replace("\\", "/") for n in HOOK_FILES]
        if not all(w in blob.replace("\\\\", "/") for w in want):
            bad.append(rel)
    return bad


def main(argv=None):
    common.stdio_utf8()
    argv = sys.argv[1:] if argv is None else argv
    root = HERE.parent if (HERE.parent / ".space").is_dir() and HERE.name == ".space" else None
    if argv and argv[0] == "--target":
        root = Path(argv[1])
    if root is None:
        print("usage: python3 .space/install_hooks.py  (inside a Space)  or  --target <Space>", file=sys.stderr)
        return 2
    report = install(root)
    left = missing(root)
    print(json.dumps({"ok": not left, "files": report, "missing": left}, ensure_ascii=False, indent=2))
    return 0 if not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
