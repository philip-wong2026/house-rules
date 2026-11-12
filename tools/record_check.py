#!/usr/bin/env python3
"""Record check: a project folder changed but its "Current status" did not keep up -> name it.

Read-only. Config: config.json "record_check":
  {"grace_days": 2, "projects": [{"name": "Garden", "folder": "projects/garden",
                                   "state": "work/STATE.md", "key": "Garden",
                                   "readme": "projects/garden/README.md", "skip": ["output/"]}]}
The progress record is the project README section "## Current status" (or "## 当前状态");
the module STATE entry is the fallback. The newer of the two dates counts. Dates later than
today are plans, not records. Formats read: 2026-11-05, 11/5, 11月5日.

Usage: python3 .space/record_check.py [--json]
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKIP_NAMES = ("-NSConflict", ".DS_Store", "~$", "(conflicted copy", ".sync-conflict-")
STATUS_HEADING = re.compile(r"^(#{1,6})\s*(current status|当前状态)", re.I)

M = {
    "missing": ("{name}: changed {changed}, but no entry found in {state} and the README has no "
                "\"Current status\" section (check record_check in config.json)",
                "{name}：{changed} 有改动，但 {state} 里找不到对应条目，README 也没有「当前状态」一节"),
    "no_date": ("{name}: changed {changed}, but the entry in {state} has no date",
                "{name}：{changed} 有改动，但 {state} 里这一条没写日期"),
    "stale": ("{name}: files changed {changed}, {state} only records up to {entry} ({gap} days behind)",
              "{name}：文件改到 {changed}，{state} 里只记到 {entry}（差 {gap} 天）"),
    "folder_missing": ("{name}: project folder not found, check the config", "{name}：找不到项目文件夹，检查配置"),
    "ok": ("All project records are up to date.", "全部项目的记录都跟上了。"),
}


def latest_change(folder, skip):
    best, name = None, ""
    for f in Path(folder).rglob("*"):
        if not f.is_file() or any(s in f.name for s in SKIP_NAMES):
            continue
        rel = f.relative_to(folder).as_posix()
        if any(part.startswith(".") for part in rel.split("/")):
            continue
        if any(rel == s or rel.startswith(s.rstrip("/") + "/") for s in skip):
            continue
        t = f.stat().st_mtime
        if best is None or t > best:
            best, name = t, rel
    return (dt.datetime.fromtimestamp(best).astimezone().date() if best else None), name


def _resolve_year(m, d, today):
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            c = dt.date(y, m, d)
        except ValueError:
            continue
        if best is None or abs((c - today).days) < abs((best - today).days):
            best = c
    return best


def block_date(block, today):
    dates = []
    for y, m, d in re.findall(r"(20\d\d)-(\d{1,2})-(\d{1,2})", block):
        try:
            dates.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    pairs = re.findall(r"(?<![\d/-])(\d{1,2})/(\d{1,2})(?![\d/])", block) + re.findall(r"(?<!\d)(\d{1,2})月(\d{1,2})日", block)
    for m, d in pairs:
        m, d = int(m), int(d)
        if 1 <= m <= 12 and 1 <= d <= 31:
            c = _resolve_year(m, d, today)
            if c:
                dates.append(c)
    past = [x for x in dates if x <= today]
    return max(past) if past else dt.date.min


def _norm(text):
    return text.replace("**", "").replace("：", ":").strip()


def entry_date(state, key, today):
    lines = Path(state).read_text(encoding="utf-8").splitlines()
    nkey = _norm(key)
    for i, line in enumerate(lines):
        if nkey in _norm(line):
            if line.lstrip().startswith("#"):
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith("#"):
                    j += 1
                block = " ".join(lines[i:j])
            else:
                block = line
            return block_date(block, today)
    return None


def readme_date(readme, today):
    readme = Path(readme)
    if not readme.exists():
        return None
    lines = readme.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = STATUS_HEADING.match(line.strip())
        if m:
            lvl = len(m.group(1))
            j = i + 1
            while j < len(lines):
                h = re.match(r"^(#{1,6})\s", lines[j].strip())
                if h and len(h.group(1)) <= lvl:
                    break
                j += 1
            return block_date(" ".join(lines[i:j]), today)
    return None


def check(root=ROOT, today=None):
    root = Path(root).resolve()
    cfg = common.load_config(root)
    today = today or common.now_local().date()
    grace = cfg["record_check"].get("grace_days", 2)
    out = []
    for p in cfg["record_check"]["projects"]:
        folder, state = root / p["folder"], root / p["state"]
        changed, fname = latest_change(folder, p.get("skip", [])) if folder.exists() else (None, "")
        st = entry_date(state, p["key"], today) if state.exists() else None
        readme_rel = p.get("readme", p["folder"] + "/README.md")
        rd = readme_date(root / readme_rel, today)
        if rd is not None and (st is None or rd >= st):
            written, where = rd, readme_rel
        else:
            written, where = st, p["state"]
        row = {"name": p["name"], "changed": str(changed), "file": fname, "state": where,
               "entry": None if written is None else ("no date" if written == dt.date.min else str(written))}
        if changed is None:
            row["status"] = "folder_missing"
        elif written is None:
            row["status"] = "missing"
        elif written == dt.date.min:
            row["status"] = "no_date"
        elif (changed - written).days >= grace:
            row["status"] = "stale"
            row["gap_days"] = (changed - written).days
        else:
            row["status"] = "ok"
        out.append(row)
    return out


def nag_lines(rows, lang="en"):
    msgs = []
    for r in rows:
        if r["status"] == "ok":
            continue
        msgs.append("- " + common.tr(M, lang, r["status"], name=r["name"], changed=r["changed"], state=r["state"],
                                     entry=r["entry"], gap=r.get("gap_days", 0)))
    return msgs


def main(argv=None, root=ROOT):
    common.stdio_utf8()
    argv = sys.argv[1:] if argv is None else argv
    lang = common.load_config(root)["language"]
    rows = check(root)
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        lines = nag_lines(rows, lang)
        print("\n".join(lines) if lines else common.tr(M, lang, "ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
