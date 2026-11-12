#!/usr/bin/env python3
"""Back up a file before you edit it.

Usage: python3 .space/backup.py <file> [<file> ...]
Copies each file into <history_dir>/write-backups/<YYYY-MM-DD>/<original relative path>,
with @HHMMSS added to the file name. Never overwrites an earlier backup. Files outside the
Space root go under _outside_space/. Exit code 1 means a backup failed: do not edit that file.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

M = {
    "not_file": ("Not a file: {path}", "不是文件：{path}"),
    "mismatch": ("Backup verification failed: {path}", "备份核对不一致：{path}"),
    "done": ("Backed up: {path}", "已备份：{path}"),
    "failed": ("Backup failed: {path}: {why}", "备份失败：{path}：{why}"),
}


def backup(src, root=ROOT, now=None):
    root = Path(root).resolve()
    cfg = common.load_config(root)
    base = root / cfg["history_dir"] / "write-backups"
    now = now or common.now_local()
    src = Path(src).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(common.tr(M, cfg["language"], "not_file", path=src))
    try:
        rel = src.relative_to(root)
    except ValueError:
        drive = src.drive.replace(":", "").replace("\\", "").replace("/", "")
        rel = Path("_outside_space") / drive / src.relative_to(src.anchor)
    stamp = now.strftime("%H%M%S")
    dest = base / now.strftime("%Y-%m-%d") / rel.parent / f"{src.stem}@{stamp}{src.suffix}"
    n = 1
    while dest.exists():
        n += 1
        dest = dest.with_name(f"{src.stem}@{stamp}-{n}{src.suffix}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    if dest.read_bytes() != src.read_bytes():
        raise OSError(common.tr(M, cfg["language"], "mismatch", path=dest))
    return dest


def main(argv, root=ROOT):
    common.stdio_utf8()
    lang = common.load_config(root)["language"]
    if not argv:
        print(__doc__)
        return 2
    code = 0
    for item in argv:
        try:
            dest = backup(item, root)
            print(common.tr(M, lang, "done", path=dest.relative_to(Path(root).resolve()).as_posix()))
        except Exception as exc:  # noqa: BLE001
            print(common.tr(M, lang, "failed", path=item, why=exc), file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
