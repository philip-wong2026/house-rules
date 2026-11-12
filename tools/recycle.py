#!/usr/bin/env python3
"""Space recycle bin: move files into a bin instead of deleting them. Standard library only.

Recycle: python3 .space/recycle.py <path...> --reason "why" --who <name>
Restore: python3 .space/recycle.py --restore .space/recycle-bin/<date>/<original path>
Empty:   python3 .space/recycle.py --empty      (only date folders older than the keep period)
--dry-run lists what would happen. Protected paths (config protected_paths, history, hooks,
backups, originals, secrets, README/STATE/rules files) are refused. Permanent deletion is
never done here except --empty after the keep period.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SECRET_SUFFIXES = {".env", ".pem", ".key", ".p12", ".pfx", ".keystore", ".kdbx"}
RULE_NAMES = {"readme.md", "state.md", "agents.md", "claude.md", "principles.md"}
BUILTIN_PROTECTED = (".space/hooks", ".claude")

M = {
    "outside": ("Refused: path is outside the Space: {raw}", "拒绝：Space 以外的路径：{raw}"),
    "symlink": ("Refused: symbolic link in path, cannot confirm the boundary: {rel}",
                "拒绝：路径含符号链接，不能确认回收边界：{rel}"),
    "word": ("Refused: protected name (original/secret/history/backup...): {rel}",
             "拒绝：原件／敏感／正本保护范围不能回收：{rel}"),
    "secret": ("Refused: credential file: {rel}", "拒绝：凭据文件不能回收：{rel}"),
    "rules": ("Refused: rules or state file: {rel}", "拒绝：规则／正本文件不能回收：{rel}"),
    "backup": ("Refused: backups cannot be recycled: {rel}", "拒绝：备份不能回收：{rel}"),
    "top": ("Refused: the Space root or a top-level folder cannot be moved as a whole: {rel}",
            "拒绝：Space 根目录或一级目录不能整体挪走：{rel}"),
    "prefix": ("Refused: protected folder (or a parent of it): {prefix}",
               "拒绝：受保护目录（或包含它的上级）不能回收：{prefix}"),
    "conflict": ("Refused: sync-conflict copies are evidence, handle them by hand: {rel}",
                 "拒绝：同步冲突副本是证据，请人工处理：{rel}"),
    "link_in_dir": ("Refused: symbolic link inside folder: {rel}", "拒绝：目录中含符号链接：{rel}"),
    "special": ("Refused: not a regular file or folder: {rel}", "拒绝：不是普通文件或目录：{rel}"),
    "missing": ("Refused: path does not exist: {rel}", "拒绝：路径不存在：{rel}"),
    "overlap": ("Refused: duplicate or nested paths in one batch: {rel}",
                "拒绝：同一批路径重复或互相包含：{rel}"),
    "taken": ("Refused: target was just taken: {rel}", "拒绝：目标刚被占用：{rel}"),
    "restore_where": ("Refused: --restore needs a full path inside the recycle bin",
                      "拒绝：--restore 必须提供回收站内的完整路径"),
    "restore_date": ("Refused: restore path must be inside a dated folder of the bin",
                     "拒绝：捞回路径必须位于回收站的日期目录内"),
    "no_record": ("Refused: no valid recycle record for this item; the original place is never guessed",
                  "拒绝：找不到这项的有效回收记录；不猜原位置"),
    "exists": ("Refused: something already exists at the original place, not overwriting: {source}",
               "拒绝：原位置已有文件或目录，不覆盖：{source}"),
    "busy": ("Another recycle/restore/empty run is in progress; nothing done.",
             "另一次回收／捞回／清空正在运行，本次未操作"),
    "need_args": ("Recycling needs paths, --reason and --who", "回收须提供路径、--reason 和 --who"),
    "mix": ("--empty / --restore cannot be combined with paths", "--empty／--restore 不能同时带回收路径"),
    "failed": ("Recycle failed: {why}", "回收失败：{why}"),
    "restored_note": ("Restored to the original place per the recycle record",
                      "按回收记录放回原位置"),
    "empty_note": ("deleted {n} files, freed {b} bytes; cutoff {cutoff}",
                   "删除{n}个文件，腾出{b}字节；截止日期{cutoff}"),
    "log_title": ("# Recycle log\n\nTimes are local. Sizes are logical bytes. Date folders older than "
                  "{days} days are emptied; this log stays.\n\n",
                  "# 回收记录\n\n时间为本机时间；大小为逻辑字节数。日期目录超过{days}天清空，记录保留。\n\n"),
    "log_head": ("| Time | Action | Who | Original path | Bin path | Bytes | Reason / result |\n"
                 "| --- | --- | --- | --- | --- | ---: | --- |\n",
                 "| 时间 | 动作 | 谁 | 原路径 | 回收站路径 | 大小（字节） | 原因／结果 |\n"
                 "| --- | --- | --- | --- | --- | ---: | --- |\n"),
    "log_conflict": ("The recycle log has an un-merged sync-conflict copy; stopping.",
                     "回收记录有未比对合入的冲突副本，停止操作"),
}


class Refused(ValueError):
    pass


def safe_path(root, raw):
    expanded = Path(raw).expanduser()
    path = Path(os.path.abspath(expanded if expanded.is_absolute() else root / expanded))
    return path


class Run:
    def __init__(self, root, now=None, dry=False, who="program", reason=""):
        self.root = Path(root).resolve()
        self.cfg = common.load_config(self.root)
        self.lang = self.cfg["language"]
        self.now = now or common.now_local()
        self.dry, self.who, self.reason = dry, who, reason
        self.bin = self.root / self.cfg["recycle_dir"]
        self.rel_bin = Path(self.cfg["recycle_dir"])
        self.events = self.bin / "events.jsonl"
        self.log = self.bin / "recycle-log.md"
        self.state = self.bin / "empty-state.json"
        for p in self.bin.glob("recycle-log*") if self.bin.exists() else []:
            if p != self.log and any(c in p.name for c in self.cfg["conflict_patterns"]):
                lines = set(self.log.read_text(encoding="utf-8").splitlines()) if self.log.exists() else set()
                if any(x not in lines for x in p.read_text(encoding="utf-8").splitlines()):
                    raise Refused(self.t("log_conflict"))

    def t(self, key, **kw):
        return common.tr(M, self.lang, key, **kw)

    def rel(self, path):
        return path.relative_to(self.root).as_posix()

    def check_path(self, raw):
        path = safe_path(self.root, raw)
        if not common.under(path, self.root):
            raise Refused(self.t("outside", raw=raw))
        cur = self.root
        for part in path.relative_to(self.root).parts:
            cur /= part
            if cur.is_symlink():
                raise Refused(self.t("symlink", rel=cur.relative_to(self.root).as_posix()))
        return path

    def reject_protected(self, path):
        rel = path.relative_to(self.root)
        text = rel.as_posix()
        lowered = [p.lower() for p in rel.parts]
        if any(w.lower() in part for part in lowered for w in self.cfg["recycle_protected_words"]):
            raise Refused(self.t("word", rel=text))
        if path.suffix.lower() in SECRET_SUFFIXES or path.name == ".env" or path.name.startswith(".env."):
            raise Refused(self.t("secret", rel=text))
        if path.name.lower() in RULE_NAMES:
            raise Refused(self.t("rules", rel=text))
        if any(part.endswith(".bak") for part in lowered):
            raise Refused(self.t("backup", rel=text))
        if rel == Path(".") or (len(rel.parts) == 1 and (path.is_dir() or rel.parts[0].startswith("."))):
            raise Refused(self.t("top", rel=text))
        history = self.cfg["history_dir"]
        for prefix in (*self.cfg["protected_paths"], *self.cfg["readonly_paths"], *BUILTIN_PROTECTED,
                       history, self.rel_bin.as_posix()):
            p = Path(prefix)
            if common.under(rel, p) or common.under(p, rel):
                raise Refused(self.t("prefix", prefix=prefix))
        if common.is_conflict_name(" ".join(rel.parts), self.cfg["conflict_patterns"]):
            raise Refused(self.t("conflict", rel=text))

    def inspect_tree(self, path, protect=False):
        count = size = 0

        def visit(p):
            nonlocal count, size
            st = p.lstat()
            if stat.S_ISLNK(st.st_mode):
                raise Refused(self.t("link_in_dir", rel=self.rel(p)))
            if protect:
                self.reject_protected(p)
            if stat.S_ISREG(st.st_mode):
                count += 1
                size += st.st_size
            elif stat.S_ISDIR(st.st_mode):
                for child in sorted(p.iterdir()):
                    visit(child)
            else:
                raise Refused(self.t("special", rel=self.rel(p)))

        visit(path)
        return count, size

    @staticmethod
    def unique(path, now):
        if not os.path.lexists(path):
            return path
        name = f"{path.name}@{now:%H%M%S}"
        dest, n = path.with_name(name), 2
        while os.path.lexists(dest):
            dest = path.with_name(f"{name}-{n}")
            n += 1
        return dest

    def note(self, action, **extra):
        event = {"time": self.now.isoformat(timespec="seconds"), "action": action, "who": self.who, **extra}
        if self.dry:
            return event
        self.bin.mkdir(parents=True, exist_ok=True)
        with self.events.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        def cell(value):
            return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

        if not self.log.exists():
            common.write_text(self.log, self.t("log_title", days=self.cfg["recycle_keep_days"]) + self.t("log_head"))
        detail = event.get("reason", "")
        if action == "empty":
            detail = self.t("empty_note", n=event["deleted"], b=event["bytes"], cutoff=event["cutoff"])
        row = [event["time"], action, self.who, event.get("source", "-"), event.get("target", "-"),
               event.get("bytes", 0), detail]
        with self.log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("| " + " | ".join(map(cell, row)) + " |\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def move(self, raws):
        sources = [self.check_path(raw) for raw in raws]
        for i, src in enumerate(sources):
            if not src.exists() and not src.is_symlink():
                raise Refused(self.t("missing", rel=self.rel(src)))
            self.reject_protected(src)
            if any(common.under(src, other) or common.under(other, src) for other in sources[:i]):
                raise Refused(self.t("overlap", rel=self.rel(src)))
            self.inspect_tree(src, protect=True)
        results = []
        for src in sources:
            count, size = self.inspect_tree(src, protect=True)
            dest = self.unique(self.bin / f"{self.now:%Y-%m-%d}" / self.rel(src), self.now)
            if not self.dry:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if os.path.lexists(dest):
                    raise Refused(self.t("taken", rel=self.rel(dest)))
                src.rename(dest)
            results.append(self.note("recycle", source=self.rel(src), target=self.rel(dest),
                                     bytes=size, files=count, reason=self.reason))
        return results

    def active_items(self):
        active = {}
        if not self.events.exists():
            return active
        for line in self.events.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["action"] == "recycle":
                active[event["target"]] = (datetime.fromisoformat(event["time"]), event["source"])
            elif event["action"] == "restore":
                active.pop(event["target"], None)
            elif event["action"] == "empty":
                for key in list(active):
                    if any(common.under(Path(key), Path(day)) for day in event["days"]):
                        del active[key]
        return active

    def restore(self, raw):
        src = self.check_path(raw)
        if not common.under(src, self.bin):
            raise Refused(self.t("restore_where"))
        rel = src.relative_to(self.bin)
        if len(rel.parts) < 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rel.parts[0]):
            raise Refused(self.t("restore_date"))
        found = self.active_items().get(self.rel(src))
        if found is None:
            raise Refused(self.t("no_record"))
        source = found[1]
        dest = self.check_path(source)
        self.reject_protected(dest)
        if os.path.lexists(dest):
            raise Refused(self.t("exists", source=source))
        count, size = self.inspect_tree(src)
        if not self.dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
        return self.note("restore", source=source, target=self.rel(src), bytes=size, files=count,
                         reason=self.reason or self.t("restored_note"))

    def expire(self):
        keep = self.cfg["recycle_keep_days"]
        cutoff = (self.now - timedelta(days=keep)).date()
        active = self.active_items()
        days, count, size = [], 0, 0
        if self.bin.exists():
            for d in sorted(self.bin.iterdir()):
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name) or not d.is_dir():
                    continue
                try:
                    if date.fromisoformat(d.name) >= cutoff:
                        continue
                except ValueError:
                    continue
                n, b = self.inspect_tree(d)
                events = {t: info for t, info in active.items() if common.under(Path(t), Path(self.rel(d)))}
                if not events or any(at >= self.now - timedelta(days=keep) for at, _ in events.values()):
                    continue
                files = [p for p in d.rglob("*") if p.is_file()]
                if any(not any(common.under(Path(self.rel(p)), Path(t)) for t in events) for p in files):
                    continue
                days.append(d)
                count, size = count + n, size + b
        for d in days:
            if not self.dry:
                shutil.rmtree(d)
        result = self.note("empty", deleted=count, bytes=size, days=[self.rel(d) for d in days],
                           cutoff=cutoff.isoformat())
        if not self.dry:
            self.state.write_text(json.dumps({"updated_at": result["time"], "deleted": count, "bytes": size},
                                             indent=1) + "\n", encoding="utf-8")
        return result


class Lock:
    def __init__(self, root):
        digest = hashlib.sha256(os.fsencode(str(root))).hexdigest()[:20]
        self.path = Path(tempfile.gettempdir()) / f"house-rules-recycle-{digest}.lock"
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise Refused("busy") from None
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
            try:
                self.path.unlink()
            except OSError:
                pass


def main(argv=None, root=ROOT):
    common.stdio_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--restore", dest="restore")
    mode.add_argument("--empty", dest="clear", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--who", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    cfg = common.load_config(root)
    lang = cfg["language"]
    try:
        if (a.clear or a.restore) and a.paths:
            raise Refused(common.tr(M, lang, "mix"))
        if not a.clear and not a.restore and (not a.paths or not a.reason.strip() or not a.who.strip()):
            raise Refused(common.tr(M, lang, "need_args"))
        try:
            with Lock(Path(root).resolve()):
                run = Run(root, dry=a.dry_run, who=a.who or "program", reason=a.reason)
                result = run.expire() if a.clear else run.restore(a.restore) if a.restore else run.move(a.paths)
        except Refused as exc:
            if str(exc) == "busy":
                raise Refused(common.tr(M, lang, "busy")) from None
            raise
        print(json.dumps({"now": run.now.isoformat(timespec="seconds"), "dry_run": a.dry_run,
                          "result": result}, ensure_ascii=False, indent=1))
        return 0
    except (OSError, ValueError) as exc:
        print(common.tr(M, lang, "failed", why=exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
