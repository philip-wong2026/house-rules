#!/usr/bin/env python3
"""Read-only health check of the Space: sizes, links, conflict copies, stray backups.

Usage: python3 .space/state_check.py [--root DIR]   (prints JSON; exit 1 when there are errors)

Checks (limits come from config.json):
- required files exist, are non-empty UTF-8 (config required_files)
- root STATE.md and each module STATE.md within their size limit; 80% gives a warning
- no per-round dated headings in STATE files (history belongs in dated record files)
- local Markdown links in STATE files point to files that exist; root STATE links every module
- each README "## Current status" section within its limit (notice only)
- records over the line/byte limit in config record_dirs
- sync-conflict copies (only when uses_sync_drive is true), minus those registered as kept in
  .space/conflict-registry.json (path + SHA-256)
- .bak files left next to originals (use .space/backup.py instead)
- backup status still "pending" (offsite backup not confirmed)
It does not prove anyone understood the rules and is not an access-control mechanism.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ".space/conflict-registry.json"
BAK = re.compile(r"\.bak(?:[-_.]|$)", re.I)
STATUS_SECTION = re.compile(r"^##[ \t]*(?:current status|当前状态)[^\n]*\n.*?(?=^##[ \t]|\Z)", re.M | re.S | re.I)
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".log", ".csv", ".py", ".yml", ".yaml"}

M = {
    "missing": ("{name}: {why}", "{name}：{why}"),
    "empty": ("{name}: file is empty", "{name}：内容为空"),
    "over": ("{name}: {n} characters, over the {limit} limit; tidy up first, never truncate",
             "{name}：{n}字符，超过{limit}上限；先整理，不硬截断"),
    "eighty": ("{name}: at 80% of the limit; merge duplicates and move closed history to dated records",
               "{name}：达到80%，先归档闭合过程并合并重复"),
    "dated_heading": ("{name}: has per-round dated headings; keep history in dated record files",
                      "{name}：存在逐轮日期标题；过程应另存日期记录"),
    "broken_link": ("{name}: link target missing: {label} -> {url}", "{name}：链接不存在：{label} -> {url}"),
    "no_module_link": ("root STATE.md does not link module: {m}", "根STATE缺少模块入口：{m}"),
    "record_big": ("{file}: {lines} lines / {bytes} bytes, over the {max_lines}-line / {max_bytes}-byte limit; "
                   "move evidence out of the Space and keep a conclusion plus a pointer",
                   "{file}：{lines}行/{bytes}字节，超过{max_lines}行或{max_bytes}字节；证据移出，只留结论和指针"),
    "bak": ("{n} new .bak file(s) beside originals: {names}; use python3 .space/backup.py instead",
            "正本旁新出现{n}份 .bak 备份：{names}；改用 .space/backup.py"),
    "conflicts": ("{n} unregistered or changed sync-conflict copies; compare, keep both sides, then merge",
                  "发现{n}份未登记或内容已变化的同步冲突副本；先比对、保全双方再合并"),
    "registered_gone": ("Registered conflict copy no longer exists: {name}", "已登记冲突副本不存在：{name}"),
    "registry_bad": ("{reg}: cannot read: {why}", "{reg}：无法读取：{why}"),
    "readme_over": ("{file}: \"Current status\" is {n} characters, over {limit}; the project session should move "
                    "closed history out", "{file}“当前状态”{n}字，超过{limit}上限；由项目会话整理"),
    "readme_80": ("{file}: \"Current status\" at 80% of the limit", "{file}“当前状态”{n}字，达到80%"),
    "backup_pending": ("Offsite backup is not confirmed yet (config backup.status = pending); see BACKUP.md",
                       "异地备份尚未确认（config 中 backup.status = pending）；见 BACKUP.md"),
    "dates": ("{n} key date(s) copied outside their source: {names}", "{n}处在正本以外抄写了关键日期：{names}"),
    "tool_failed": ("{tool} did not run: {why}", "{tool}没跑成：{why}"),
    "scope": ("File checks only; does not prove understanding, review, sync or client enforcement",
              "只读文件检查，不证明理解、业务审核、同步或客户端强制执行"),
}


def _walk(root, cfg):
    skip_rel = {cfg["history_dir"], cfg["recycle_dir"]}
    for base, dirs, files in os.walk(root):
        rel_base = Path(base).relative_to(root).as_posix()
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and (f"{rel_base}/{d}" if rel_base != "." else d) not in skip_rel)
        yield Path(base), dirs, sorted(files)


def registered(root):
    try:
        items = json.loads((Path(root) / REGISTRY).read_text(encoding="utf-8"))["registered"]
    except FileNotFoundError:
        return {}
    return {i["file"]: i for i in items}


def conflicts(root, cfg=None):
    root = Path(root).resolve()
    cfg = cfg or common.load_config(root)
    if not cfg["uses_sync_drive"]:
        return []
    found = []
    pats = cfg["conflict_patterns"]
    for base, _, files in _walk(root, cfg):
        for name in files:
            if not common.is_conflict_name(name, pats):
                continue
            path = base / name
            other_name = name
            for p in pats:
                other_name = other_name.replace(p, "", 1) if p in other_name else other_name
            other = path.with_name(other_name)
            st = path.stat()
            found.append({"file": path.relative_to(root).as_posix(),
                          "counterpart": other.relative_to(root).as_posix(),
                          "counterpart_exists": other.exists(), "bytes": st.st_size,
                          "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")})
    return found


def classify(root, cfg=None):
    """(unregistered_or_changed, registered_kept, registered_but_missing)."""
    root = Path(root).resolve()
    known = registered(root)
    found, kept = [], []
    for c in conflicts(root, cfg):
        item = known.pop(c["file"], None)
        if item and hashlib.sha256((root / c["file"]).read_bytes()).hexdigest() == item["sha256"]:
            kept.append({**c, "status": "registered-kept", "note": item.get("note")})
            continue
        if item:
            c["status"] = "registered-but-changed"
        found.append(c)
    return found, kept, known


def oversized_records(root, cfg):
    root = Path(root).resolve()
    lim = cfg["limits"]
    out = []
    for d in cfg["record_dirs"]:
        folder = root / d
        if not folder.exists():
            continue
        for base, _, files in _walk(folder, cfg):
            for name in files:
                path = base / name
                if path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                data = path.read_bytes()
                lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
                if lines > lim["record_lines"] or len(data) > lim["record_bytes"]:
                    out.append({"file": path.relative_to(root).as_posix(), "lines": lines, "bytes": len(data)})
    return out


def readme_status(root, cfg):
    root = Path(root).resolve()
    limit = cfg["limits"]["readme_status_chars"]
    rows, notes = [], []
    for base, dirs, files in _walk(root, cfg):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "README.md" not in files:
            continue
        path = base / "README.md"
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        m = STATUS_SECTION.search(body)
        if not m:
            continue
        rel, n = path.relative_to(root).as_posix(), len(m.group(0))
        rows.append({"file": rel, "characters": n, "limit": limit})
        if n > limit:
            notes.append(("readme_over", {"file": rel, "n": n, "limit": limit}))
        elif n >= limit * .8:
            notes.append(("readme_80", {"file": rel, "n": n}))
    return rows, notes


def stray_baks(root, cfg):
    root = Path(root).resolve()
    found = []
    for base, dirs, files in _walk(root, cfg):
        dirs[:] = [d for d in dirs if not (base == root and d.startswith("."))]
        found += [(base / n).relative_to(root).as_posix() for n in files if BAK.search(n)]
    return sorted(found)


def check(root=ROOT):
    root = Path(root).resolve()
    cfg = common.load_config(root)
    lang = cfg["language"]

    def t(key, **kw):
        return common.tr(M, lang, key, **kw)

    errors, warnings, rows = [], [], []
    for name in cfg["required_files"]:
        try:
            if not (root / name).read_text(encoding="utf-8").strip():
                errors.append(t("empty", name=name))
        except (OSError, UnicodeError) as exc:
            errors.append(t("missing", name=name, why=exc))
    names = [("STATE.md", cfg["limits"]["root_state_chars"])] + \
            [(f"{m}/STATE.md", cfg["limits"]["module_state_chars"]) for m in cfg["modules"]]
    for name, limit in names:
        path = root / name
        try:
            raw = path.read_bytes()
            body = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(t("missing", name=name, why=exc))
            continue
        if not body.strip():
            errors.append(t("empty", name=name))
        if len(body) > limit:
            errors.append(t("over", name=name, n=len(body), limit=limit))
        elif len(body) >= limit * .8:
            warnings.append(t("eighty", name=name))
        if re.search(r"^#{1,6}\s+20\d{2}[-年/]", body, re.M):
            errors.append(t("dated_heading", name=name))
        for label, target in re.findall(r"\[([^]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)", body):
            url = target.strip("<>")
            if url.startswith("#") or urlsplit(url).scheme:
                continue
            clean = unquote(url.split("#", 1)[0].split("?", 1)[0])
            if clean and not (path.parent / clean).exists():
                errors.append(t("broken_link", name=name, label=label, url=url))
        if name == "STATE.md":
            for m in cfg["modules"]:
                if f"]({m}/STATE.md)" not in body:
                    errors.append(t("no_module_link", m=m))
        rows.append({"file": name, "characters": len(body), "limit": limit, "bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    big = oversized_records(root, cfg)
    for r in big:
        errors.append(t("record_big", max_lines=cfg["limits"]["record_lines"],
                        max_bytes=cfg["limits"]["record_bytes"], **r))
    readmes, notes = readme_status(root, cfg)
    notices = [t(k, **kw) for k, kw in notes]
    baks = stray_baks(root, cfg)
    if baks:
        warnings.append(t("bak", n=len(baks), names=", ".join(baks[:5])))
    try:
        found, kept, known = classify(root, cfg)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        found, kept, known = conflicts(root, cfg), [], {}
        errors.append(t("registry_bad", reg=REGISTRY, why=exc))
    if found:
        warnings.append(t("conflicts", n=len(found)))
    for name in known:
        warnings.append(t("registered_gone", name=name))
    if cfg.get("backup", {}).get("status") != "done":
        warnings.append(t("backup_pending"))
    try:
        import date_copy_check
        hits = date_copy_check.scan(root)
        if hits:
            warnings.append(t("dates", n=len(hits), names=", ".join(f"{h['file']}:{h['line']}" for h in hits[:5])))
    except Exception as exc:  # noqa: BLE001
        warnings.append(t("tool_failed", tool="date_copy_check", why=exc))
    return {"ok": not errors, "files": rows, "oversized_records": big, "readme_status": readmes,
            "notices": notices, "conflicts": found, "registered_conflicts": kept,
            "warnings": warnings, "errors": errors, "scope": t("scope")}


def main(argv=None):
    common.stdio_utf8()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = check(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
