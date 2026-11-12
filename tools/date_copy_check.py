#!/usr/bin/env python3
"""Key-date copy check: a key date should be written in ONE place only.

Reads config.json "key_dates", a list of
  {"item": "Project launch", "keywords": "launch|go-live", "sources": ["projects/launch/README.md"]}
and reports lines in other "live" files (README, STATE, AGENTS, ...) where a keyword has a
date within 16 characters. Lines with correction marks (~~, superseded, outdated, ...) are
left alone. Read-only. Fix by writing "see key dates" instead of the date.

Usage: python3 .space/date_copy_check.py        (JSON; exit 1 when copies are found)
Optional tool: with no key_dates configured it reports nothing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATE = re.compile(r"(?<!\d)(?<!\d\.)(?:20\d{2}[-/年])?(?:0?[1-9]|1[0-2])\s?(?:/|月|-)\s?(?:[12]\d|3[01]|0?[1-9])(?:日|号)?(?!\d|\.\d)")
SKIP = (".space/", "history", "archive", "/records/", "recycle-bin", "node_modules", "conflict")
TRACE = re.compile(r"~~|superseded|outdated|corrected|was written|no longer|作废|过时|更正|原写|已改为|不再是")
CODE = re.compile(r"python3? |--date|^\s*`|^\s*\$ ")
NEAR = 16


def live(rel, names):
    return rel.rsplit("/", 1)[-1] in names and not any(s in "/" + rel.lower() for s in SKIP)


def scan(root=ROOT):
    root = Path(root).resolve()
    cfg = common.load_config(root)
    items = cfg["key_dates"]
    if not items:
        return []
    names = set(cfg["live_file_names"])
    hits = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if not live(rel, names):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for no, line in enumerate(lines, 1):
            if TRACE.search(line) or CODE.search(line) or not DATE.search(line):
                continue
            for item in items:
                if any(rel == s or (s.endswith("/") and rel.startswith(s)) for s in item["sources"]):
                    continue
                kw = re.compile(item["keywords"], re.I)
                if any(DATE.search(line[max(0, m.start() - NEAR):m.end() + NEAR]) for m in kw.finditer(line)):
                    hits.append({"file": rel, "line": no, "item": item["item"], "text": " ".join(line.split())[:120]})
                    break
    return hits


def main(root=ROOT):
    common.stdio_utf8()
    hits = scan(root)
    print(json.dumps({"ok": not hits, "hits": len(hits), "details": hits,
                      "fix": "replace the date with 'see key dates'; the source is listed in config.json key_dates"},
                     ensure_ascii=False, indent=1))
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
