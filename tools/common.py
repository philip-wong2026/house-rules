"""Shared helpers for Space Open tools. Standard library only; Python 3.9+; macOS / Windows / Linux."""
from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DEFAULTS = {
    "language": "en",
    "uses_sync_drive": False,
    "conflict_patterns": ["-NSConflict", " (conflicted copy", ".sync-conflict-"],
    "modules": ["system"],
    "protected_paths": [],
    "readonly_paths": [],
    "recycle_protected_words": ["original", "evidence", "ledger", "register", "credential",
                                "secret", "private", "archive", "history", "backup", "receipt"],
    "required_files": ["AGENTS.md", "CLAUDE.md", "STATE.md", "PRINCIPLES.md"],
    "limits": {"root_state_chars": 2000, "module_state_chars": 6000, "readme_status_chars": 3000,
               "record_lines": 300, "record_bytes": 30000},
    "record_dirs": [],
    "shared_files": ["STATE.md"],
    "record_check": {"grace_days": 2, "projects": []},
    "key_dates": [],
    "live_file_names": ["README.md", "STATE.md", "AGENTS.md", "CLAUDE.md", "PRINCIPLES.md"],
    "recycle_keep_days": 30,
    "history_dir": ".space/history",
    "recycle_dir": ".space/recycle-bin",
    "backup": {"status": "pending", "method": ""},
}


def stdio_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def read_stdin_text():
    try:
        return sys.stdin.buffer.read().decode("utf-8")
    except (AttributeError, UnicodeError):
        return sys.stdin.read()


def merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(root):
    path = Path(root) / ".space" / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    return merge(DEFAULTS, data)


def tr(catalog, lang, key, **kw):
    pair = catalog[key]
    text = pair[1] if lang == "zh-CN" and len(pair) > 1 else pair[0]
    return text.format(**kw) if kw else text


def now_local():
    return datetime.now().astimezone()


def norm(path):
    return os.path.normcase(str(path))


def under(path, parent):
    path, parent = Path(path), Path(parent)
    return path == parent or parent in path.parents


def is_conflict_name(name, patterns):
    return any(p in name for p in patterns)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
