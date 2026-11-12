#!/usr/bin/env python3
"""Read-only rule delivery: hand the required rule files to an AI in checked, numbered parts.

  python3 .space/read_rules.py manifest
  python3 .space/read_rules.py read <file> --part N [--expected-sha SHA]

`manifest` checks that every required file (config required_files) exists, is non-empty UTF-8
and lists size, SHA-256 and part count. It proves the files are complete, not that the AI
understood or follows them. Private folders and non-Markdown files are never delivered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PART_SIZE = 2400
FORBIDDEN = {"private", "credentials", "history", "backup", "backups", "recycle-bin"}

M = {
    "outside": ("Only Markdown rule files inside this Space can be read here",
                "仅允许读取当前Space内的Markdown规则文件"),
    "forbidden": ("This tool does not read private, history or non-Markdown files",
                  "此工具不读取私密、历史或非Markdown文件"),
    "empty": ("Required file is empty: {rel}", "必读文件为空：{rel}"),
    "changed": ("The file changed; fetch the manifest again and re-read from the new version",
                "文件版本已改变；重新取得manifest并从新版本全文重读"),
    "range": ("Part out of range; need 1 to {n}", "分段超出范围；需要1至{n}"),
    "claim": ("File completeness check only; no body delivered, proves neither understanding nor compliance",
              "文件完备检查；尚未提供正文，不证明理解或强制遵守"),
    "stop": ("Read failed, stop the task: {why}", "读取失败，停止业务：{why}"),
}


def load(root, name, lang="en"):
    root = Path(root).resolve()
    path = (root / name).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError(common.tr(M, lang, "outside")) from None
    if any(part.lower() in FORBIDDEN for part in relative.parts) or path.suffix != ".md":
        raise ValueError(common.tr(M, lang, "forbidden"))
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if not text.strip():
        raise ValueError(common.tr(M, lang, "empty", rel=relative.as_posix()))
    return text, {
        "file": relative.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "characters": len(text),
        "lines": len(text.splitlines()),
        "parts": (len(text) + PART_SIZE - 1) // PART_SIZE,
    }


def inspect(root):
    cfg = common.load_config(root)
    return [load(root, name, cfg["language"])[1] for name in cfg["required_files"]]


def deliver(root, name, part, expected=None):
    lang = common.load_config(root)["language"]
    inspect(root)
    text, info = load(root, name, lang)
    if expected is not None and info["sha256"] != expected:
        raise ValueError(common.tr(M, lang, "changed"))
    if part < 1 or part > info["parts"]:
        raise ValueError(common.tr(M, lang, "range", n=info["parts"]))
    start = (part - 1) * PART_SIZE
    end = min(part * PART_SIZE, len(text))
    fragment = text[start:end]
    metadata = {**info, "part": part, "character_range": [start + 1, end],
                "fragment_sha256": hashlib.sha256(fragment.encode("utf-8")).hexdigest()}
    return metadata, fragment


def main(argv=None, root=ROOT):
    common.stdio_utf8()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(root))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("manifest")
    read = commands.add_parser("read")
    read.add_argument("file")
    read.add_argument("--part", type=int, required=True)
    read.add_argument("--expected-sha")
    args = parser.parse_args(argv)
    lang = common.load_config(args.root)["language"]
    try:
        if args.command == "manifest":
            print(json.dumps({"required": inspect(args.root), "part_size": PART_SIZE,
                              "claim": common.tr(M, lang, "claim")}, ensure_ascii=False))
        else:
            metadata, fragment = deliver(args.root, args.file, args.part, args.expected_sha)
            header = json.dumps(metadata, ensure_ascii=False)
            print("BEGIN " + header)
            sys.stdout.write(fragment)
            print("\nEND " + header)
    except (OSError, UnicodeError, ValueError) as error:
        print(common.tr(M, lang, "stop", why=error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
