#!/usr/bin/env python3
"""Claude Code SessionStart / UserPromptSubmit hook: run the state check every turn (skeleton).

Prints nothing when all is well. Otherwise prints a short notice that enters the turn's context:
unregistered sync-conflict copies, warnings and errors from state_check.py. Read-only, never
blocks the conversation. "Current status too long" is reminded only at session start.
Extend it here (for example a topic reminder when a prompt mentions a keyword) and keep it fast.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common  # noqa: E402
import state_check  # noqa: E402

ROOT = HERE.parents[1]

M = {
    "head": ("[Space turn check] handle these before starting (see AGENTS.md, start of each turn):",
             "[Space每轮检查] 动手前须处理（见 AGENTS.md 每轮开始）："),
    "conflict": ("- {file} ({status}, {mtime})", "- {file}（{status}，{mtime}）"),
    "unregistered": ("unregistered", "未登记"),
    "warn": ("- warning: {t}", "- 警告：{t}"),
    "err": ("- error: {t}", "- 错误：{t}"),
    "readme": ("[Space reminder] \"Current status\" is over the limit: {names}. Reminder only; if this is the "
               "project's main session, move closed history out before finishing.",
               "[Space提醒] 项目“当前状态”超长：{names}。只提醒；是该项目主会话时，收工前把已闭合过程移入历史。"),
    "noprotect": ("[Space reminder] No folder is registered as protected yet: the write guard only covers hook "
                  "settings, .bak files and deletions. Ask the user whether a folder (IDs, accounts, private notes) "
                  "should go into protected_paths in .space/config.json.",
                  "[Space提醒] 还没有登记任何受保护文件夹：写入检查目前只管钩子设置、.bak 和删除。"
                  "可以问用户有没有要保护的文件夹（证件、账本、私人笔记），加进 .space/config.json 的 protected_paths。"),
    "crashed": ("[Space turn check] the check script failed, run python3 .space/state_check.py by hand: {err}",
                "[Space每轮检查] 检查脚本出错，须手动运行 python3 .space/state_check.py：{err}"),
}


def notice(root, event=None):
    cfg = common.load_config(root)
    lang = cfg["language"]
    result = state_check.check(root)
    lines = [common.tr(M, lang, "conflict", file=c["file"], status=c.get("status", common.tr(M, lang, "unregistered")),
                       mtime=c["mtime"]) for c in result["conflicts"]]
    lines += [common.tr(M, lang, "warn", t=w) for w in result["warnings"]]
    lines += [common.tr(M, lang, "err", t=e) for e in result["errors"]]
    text = common.tr(M, lang, "head") + "\n" + "\n".join(lines) if lines else ""
    over = [r for r in result.get("readme_status", []) if r["characters"] > r["limit"]]
    if over and (event or {}).get("hook_event_name") == "SessionStart":
        names = ", ".join(f"{r['file']} ({r['characters']})" for r in over)
        text += ("\n" if text else "") + common.tr(M, lang, "readme", names=names)
    if (event or {}).get("hook_event_name") == "SessionStart" and not cfg.get("protected_paths"):
        text += ("\n" if text else "") + common.tr(M, lang, "noprotect")
    return text


def main(root=ROOT):
    common.stdio_utf8()
    try:
        raw = "" if sys.stdin is None or sys.stdin.isatty() else common.read_stdin_text()
        event = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        event = {}
    try:
        text = notice(root, event)
    except Exception as exc:  # noqa: BLE001
        text = common.tr(M, "en", "crashed", err=f"{type(exc).__name__}: {exc}")
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
