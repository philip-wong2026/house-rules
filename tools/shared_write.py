#!/usr/bin/env python3
"""Safe writes to shared files that two sessions might edit at the same time.

  python3 .space/shared_write.py read <path>
  python3 .space/shared_write.py write <path> --expected <SHA|null> --candidate <file>

`read` prints JSON with the whole text and its SHA-256. `write` replaces the file only if its
current SHA still equals --expected (compare-and-swap, guarded by a short lock file). If the
file changed meanwhile it exits 75: re-read, merge the newest text into your candidate, retry.
Only files listed in config.json "shared_files" are accepted. STATE files over their size limit
are refused (exit 75) so they get tidied instead of truncated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMP_EXIT = 75

M = {
    "outside": ("Path is outside the Space", "路径在Space之外"),
    "not_shared": ("Not a shared file (see config.json shared_files)", "不是共用文件（见 config.json 的 shared_files）"),
    "need_args": ("write needs --expected and --candidate", "write 需要 --expected 和 --candidate"),
    "changed": ("Target changed since you read it: re-read, merge, retry", "目标在你读取后已改变：重读、合并后重试"),
    "budget": ("STATE_BUDGET_EXCEEDED: tidy first, never truncate", "STATE 超限：先整理，禁止硬截断"),
    "locked": ("Another write holds the lock; retry shortly", "另一次写入占着锁，稍后重试"),
}


class Rejected(Exception):
    pass


def state_limit(cfg, rel):
    if rel == "STATE.md":
        return cfg["limits"]["root_state_chars"]
    if rel.endswith("/STATE.md") and rel.split("/")[0] in cfg["modules"] and rel.count("/") == 1:
        return cfg["limits"]["module_state_chars"]
    return None


def budget(cfg, rel, text):
    limit = state_limit(cfg, rel)
    if limit is None:
        return None
    return {"characters": len(text), "limit": limit, "remaining": limit - len(text),
            "status": "over" if len(text) > limit else "tidy-soon" if len(text) >= limit * .8 else "ok"}


def resolve(root, value, cfg):
    p = Path(value)
    if not value.strip() or p.is_absolute() or ".." in p.parts or "\x00" in value:
        raise Rejected(common.tr(M, cfg["language"], "outside"))
    root = Path(root).resolve()
    target = (root / p).resolve()
    if target == root or root not in target.parents:
        raise Rejected(common.tr(M, cfg["language"], "outside"))
    rel = target.relative_to(root).as_posix()
    if rel not in cfg["shared_files"]:
        raise Rejected(common.tr(M, cfg["language"], "not_shared"))
    return target, rel


def read(root, value):
    cfg = common.load_config(root)
    target, rel = resolve(root, value, cfg)
    body = target.read_bytes() if target.exists() else None
    text = body.decode("utf-8") if body is not None else ""
    result = {"path": rel, "sha256": hashlib.sha256(body).hexdigest() if body is not None else None, "text": text}
    b = budget(cfg, rel, text)
    if b:
        result["budget"] = b
    return result


def write(root, value, expected, candidate_path, wait=5.0):
    cfg = common.load_config(root)
    target, rel = resolve(root, value, cfg)
    candidate = Path(candidate_path).read_bytes().decode("utf-8")
    b = budget(cfg, rel, candidate)
    if b and b["characters"] > b["limit"]:
        raise Rejected(common.tr(M, cfg["language"], "budget"))
    lock = target.with_name(target.name + ".lock")
    deadline = time.time() + wait
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() > deadline:
                raise Rejected(common.tr(M, cfg["language"], "locked")) from None
            time.sleep(0.05)
    try:
        current = target.read_bytes() if target.exists() else None
        sha = hashlib.sha256(current).hexdigest() if current is not None else None
        if sha != (None if expected == "null" else expected):
            raise Rejected(common.tr(M, cfg["language"], "changed"))
        data = candidate.encode("utf-8")
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        return {"ok": True, "sha256": hashlib.sha256(data).hexdigest(), **({"budget": b} if b else {})}
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass


def main(argv=None, root=ROOT):
    common.stdio_utf8()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["read", "write"])
    p.add_argument("path")
    p.add_argument("--expected")
    p.add_argument("--candidate")
    a = p.parse_args(argv)
    lang = common.load_config(root)["language"]
    try:
        if a.action == "read":
            print(json.dumps(read(root, a.path), ensure_ascii=False))
            return 0
        if not a.expected or not a.candidate:
            raise Rejected(common.tr(M, lang, "need_args"))
        print(json.dumps(write(root, a.path, a.expected, a.candidate), ensure_ascii=False))
        return 0
    except Rejected as exc:
        print(json.dumps({"ok": False, "error": str(exc),
                          "next": "re-read the whole file, merge the newest text, retry with the new SHA"},
                         ensure_ascii=False))
        return TEMP_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
