#!/usr/bin/env python3
"""HouseRules installer. Standard library only; Python 3.9+; macOS / Windows / Linux.

Non-interactive (the AI asks the user the questions, then calls this with the answers):

  python3 setup.py --target ~/Space --name Alex --os mac --language en \\
      --always-on no --ai "Claude" --chat-channel "none" --modules work,personal \\
      --device "MacBook|daily computer" --sync-drive no --yes

Self-check of an installed Space:   python3 setup.py --check --target ~/Space

Existing files are never overwritten silently: they are skipped and listed, unless --force is
given, in which case the old file is first copied to <target>/.space/history/write-backups/.
.claude/settings.json is merged, never replaced. Nothing is sent anywhere.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
import backup as backup_mod  # noqa: E402
import common  # noqa: E402
import install_hooks  # noqa: E402

VERSION = "0.1.0"
RESERVED = {".space", ".claude", ".git", "templates", "tools"}
MODULE_RE = re.compile(r"^[^\W_][\w-]*$", re.UNICODE)
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
WORDS = {
    "en": ["maple", "river", "pine", "cloud", "stone", "lantern", "harbor", "meadow", "falcon", "amber"],
    "zh-CN": ["青松", "明月", "清风", "远山", "星河", "晨光", "海棠", "竹影", "秋水", "松涛"],
}
HOOK_FILES = ("pre_write_guard.py", "turn_check.py")

M = {
    "need": ("missing required option(s): {names}", "缺少必填参数：{names}"),
    "bad_module": ("invalid module name '{m}': use letters, digits, '-' or '_', no path separators",
                   "模块名不合法「{m}」：只能用字母、数字、-、_，不能含路径分隔符"),
    "no_consent": ("add --yes to confirm that the user agreed to the safety notice (their computer and data "
                   "safety is their own responsibility)",
                   "请加 --yes，表示用户已同意安全声明（电脑与数据安全由用户自己负责）"),
    "no_target": ("target path is not usable: {why}", "目标路径不可用：{why}"),
    "created": ("created", "新建"), "skipped": ("skipped (exists)", "跳过（已存在）"),
    "replaced": ("replaced (old copy backed up)", "已替换（旧版已备份）"),
    "merged": ("merged", "已合并"), "unchanged": ("unchanged", "未变"), "bad_json": ("not valid JSON, left untouched", "不是有效 JSON，未改动"),
    "left": ("unfilled placeholder in {f}: {p}", "{f} 里有未替换的占位符：{p}"),
    "done": ("Installed. Passphrase: {p}. Next: (1) self-check, run from the downloaded repo folder (keep that "
             "folder for later checks and upgrades): {py} setup.py --check --target \"{t}\"  (2) open Claude Code "
             "at {t} or one of its top-level folders and ask it for the passphrase.",
             "安装完成。暗号：{p}。下一步：①自检——回到下载的仓库文件夹运行（这个文件夹请保留，以后自检、升级还要用）："
             "{py} setup.py --check --target \"{t}\"；②在 {t} 或它的一级文件夹打开 Claude Code，问它暗号。"),
    "w_backup": ("off-site backup not confirmed yet (backup.status = pending); see BACKUP.md",
                 "异地备份还没确认（backup.status = pending）；见 BACKUP.md"),
    "w_protect": ("no protected folder registered: the write guard only covers hook settings, .bak files and "
                  "deletions; add folders to protected_paths in .space/config.json if needed",
                  "还没登记任何受保护文件夹：写入检查只管钩子设置、.bak 和删除；需要的话加进 .space/config.json 的 protected_paths"),
}


def t(lang, key, **kw):
    return common.tr(M, lang, key, **kw)


def render(text, values):
    out = PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)
    left = PLACEHOLDER.search(out)
    if left:
        raise ValueError(left.group(0))
    return out


def module_table(modules, lang):
    if lang == "zh-CN":
        rows = ["| 模块 | 文件夹 | 默认写入方 |", "|---|---|---|"]
        rows += [f"| {m} | `{m}/` | {{{{user}}}} 为这个模块开的会话（在 Space 根目录或 `{m}/` 里打开都行） |" for m in modules]
    else:
        rows = ["| Module | Folder | Default write owner |", "|---|---|---|"]
        rows += [f"| {m} | `{m}/` | the session {{{{user}}}} opens for this module (at the Space root or in `{m}/`) |" for m in modules]
    return "\n".join(rows)


def devices_table(devices, lang):
    head = ["| 设备 | 用途 |", "|---|---|"] if lang == "zh-CN" else ["| Device | Use |", "|---|---|"]
    rows = []
    for d in devices:
        name, _, use = d.partition("|")
        rows.append(f"| {name.strip()} | {use.strip() or '—'} |")
    if not rows:
        rows = ["| (add your devices) | — |"] if lang == "en" else ["| （补上你的设备） | — |"]
    return "\n".join(head + rows)


def make_passphrase(lang):
    return f"{secrets.choice(WORDS[lang])}-{secrets.choice(WORDS[lang])}-{secrets.randbelow(9000) + 1000}" \
        if lang == "en" else f"{secrets.choice(WORDS[lang])}-{secrets.randbelow(9000) + 1000}"


class Writer:
    def __init__(self, target, lang, force):
        self.target, self.lang, self.force = target, lang, force
        self.report = []
        self.now = common.now_local()

    def put(self, rel, text):
        path = self.target / rel
        if path.exists():
            if not self.force:
                self.report.append({"file": rel, "result": t(self.lang, "skipped")})
                return False
            backup_mod.backup(path, self.target, self.now)
            common.write_text(path, text)
            self.report.append({"file": rel, "result": t(self.lang, "replaced")})
            return True
        common.write_text(path, text)
        self.report.append({"file": rel, "result": t(self.lang, "created")})
        return True


def merge_settings(target, lang, python_cmd, report):
    """Hooks go to the root and every top-level folder, with absolute paths (see tools/install_hooks.py)."""
    for item in install_hooks.install(target, python_cmd):
        report.append({"file": item["file"], "result": t(lang, item["result"])})


def install(args):
    lang = args.language
    target = Path(args.target).expanduser().resolve()
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    for m in modules:
        if not MODULE_RE.match(m) or m.lower() in RESERVED:
            raise SystemExit(t(lang, "bad_module", m=m))
    py = "python" if args.os == "windows" else "python3"
    passphrase = args.passphrase or make_passphrase(lang)
    always_on_text = {
        ("yes", "en"): "yes, a computer that stays on (scheduled tasks, calling it from the phone)",
        ("no", "en"): "none yet; the main computer is not always on",
        ("yes", "zh-CN"): "有，一台常开的电脑（可跑定时任务、手机远程调用）",
        ("no", "zh-CN"): "暂时没有，主力电脑不常开",
    }[(args.always_on, lang)]
    none_word = "none yet" if lang == "en" else "暂无"
    backup_method = "(not set up yet)" if lang == "en" else "（还没设置）"
    values = {
        "user": args.name, "py": py, "date": common.now_local().date().isoformat(),
        "passphrase": passphrase, "ai": args.ai or none_word, "channel": args.chat_channel or none_word,
        "always_on": always_on_text, "backup_status": "pending", "backup_method": backup_method,
        "root_limit": common.DEFAULTS["limits"]["root_state_chars"],
        "module_limit": common.DEFAULTS["limits"]["module_state_chars"],
        "keep_days": common.DEFAULTS["recycle_keep_days"],
    }
    values["modules_table"] = render(module_table(modules, lang), values)
    values["devices_table"] = devices_table(args.device, lang)
    values["module_links"] = "\n".join(f"- [{m}]({m}/STATE.md)" for m in modules)

    target.mkdir(parents=True, exist_ok=True)
    w = Writer(target, lang, args.force)
    tdir = HERE / "templates" / lang

    def tpl(name, extra=None):
        return render((tdir / name).read_text(encoding="utf-8"), {**values, **(extra or {})})

    for name in ("AGENTS.md", "CLAUDE.md", "PRINCIPLES.md", "STATE.md", "BACKUP.md"):
        w.put(name, tpl(name))
    for name in ("state-maintenance.md", "project-three-rules.md", "agent-customization.md"):
        w.put(f".space/{name}", tpl(name))
    for m in modules:
        w.put(f"{m}/STATE.md", tpl("MODULE-STATE.md", {"module": m}))
        w.put(f"{m}/README.md", tpl("MODULE-README.md", {"module": m}))
    for src in sorted((HERE / "tools").glob("*.py")):
        w.put(f".space/{src.name}", src.read_text(encoding="utf-8"))
    for src in sorted((HERE / "tools" / "hooks").glob("*.py")):
        w.put(f".space/hooks/{src.name}", src.read_text(encoding="utf-8"))

    shared = ["STATE.md", "AGENTS.md", "CLAUDE.md"] + [f"{m}/STATE.md" for m in modules]
    config = {
        "language": lang, "uses_sync_drive": args.sync_drive == "yes", "modules": modules,
        "shared_files": shared, "protected_paths": args.protect or [], "readonly_paths": [],
        "backup": {"status": "pending", "method": ""},
    }
    w.put(".space/config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    w.put(".space/install.json", json.dumps({"version": VERSION, "os": args.os, "language": lang,
                                              "installed": common.now_local().isoformat(timespec="seconds")},
                                             indent=2) + "\n")
    if not args.no_hooks:
        merge_settings(target, lang, args.python_command or sys.executable, w.report)
    summary = {"ok": True, "target": str(target), "passphrase": passphrase, "files": w.report,
               "next": t(lang, "done", p=passphrase, t=target, py=py)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_tool(target, *argv, stdin=None):
    return subprocess.run([sys.executable, *map(str, argv)], cwd=str(target), input=stdin, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def check(args):
    target = Path(args.target).expanduser().resolve()
    cfg = common.load_config(target)
    results = []

    def record(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    for name in cfg["required_files"] + ["BACKUP.md", ".space/config.json"]:
        record(f"file {name}", (target / name).is_file())
    for m in cfg["modules"]:
        record(f"module {m}/STATE.md", (target / m / "STATE.md").is_file())
    card = (target / "CLAUDE.md").read_text(encoding="utf-8") if (target / "CLAUDE.md").is_file() else ""
    record("base card has a passphrase", bool(re.search(r"(Self-check passphrase|校验暗号)[:：]\s*\S+", card)))

    sc = run_tool(target, ".space/state_check.py")
    try:
        sc_ok = json.loads(sc.stdout)["ok"] and sc.returncode == 0
    except (ValueError, KeyError):
        sc_ok = False
    record("state_check", sc_ok, sc.stdout[-300:] if not sc_ok else "")
    rr = run_tool(target, ".space/read_rules.py", "manifest")
    record("read_rules manifest", rr.returncode == 0, rr.stderr[-200:])
    for tool in ("record_check.py", "date_copy_check.py"):
        r = run_tool(target, f".space/{tool}")
        record(tool, r.returncode == 0, (r.stdout + r.stderr)[-200:] if r.returncode else "")
    rd = run_tool(target, ".space/redact.py", "my password is hunter2")
    record("redact flags a credential", "credential" in rd.stdout, rd.stdout[-200:])

    guard = ".space/hooks/pre_write_guard.py"
    deny = json.dumps({"tool_name": "Write", "cwd": str(target),
                       "tool_input": {"file_path": str(target / ".space" / "hooks" / "x.py")}})
    ok_ev = json.dumps({"tool_name": "Write", "cwd": str(target),
                        "tool_input": {"file_path": str(target / cfg["modules"][0] / "note.md")}})
    record("write guard refuses the hook folder", run_tool(target, guard, stdin=deny).returncode == 2)
    record("write guard allows a normal note", run_tool(target, guard, stdin=ok_ev).returncode == 0)
    tc = run_tool(target, ".space/hooks/turn_check.py", stdin=json.dumps({"hook_event_name": "UserPromptSubmit"}))
    record("turn_check runs", tc.returncode == 0, tc.stderr[-200:])

    left = install_hooks.missing(target)
    record("Claude Code hooks registered (root and every top-level folder)", args.no_hooks or not left,
           "" if not left else "missing: " + ", ".join(left) + " -> python3 .space/install_hooks.py")
    lang = cfg.get("language", "en")
    warnings = []
    if cfg.get("backup", {}).get("status") != "done":
        warnings.append(t(lang, "w_backup"))
    if not cfg.get("protected_paths"):
        warnings.append(t(lang, "w_protect"))
    ok = all(r["ok"] for r in results)
    print(json.dumps({"ok": ok, "warnings": warnings, "checks": results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main(argv=None):
    common.stdio_utf8()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, help="folder to create the Space in")
    p.add_argument("--check", action="store_true", help="self-check an installed Space")
    p.add_argument("--name", help="what to call the user")
    p.add_argument("--os", choices=["mac", "windows", "linux"], help="operating system")
    p.add_argument("--language", choices=["en", "zh-CN"], default="en")
    p.add_argument("--always-on", choices=["yes", "no"], dest="always_on")
    p.add_argument("--ai", default="")
    p.add_argument("--chat-channel", default="", dest="chat_channel")
    p.add_argument("--modules", help="comma separated areas, e.g. work,personal")
    p.add_argument("--device", action="append", default=[], help='"Name|use", repeatable')
    p.add_argument("--sync-drive", choices=["yes", "no"], default="no", dest="sync_drive")
    p.add_argument("--protect", action="append", default=[], help="folder (relative) the write guard protects")
    p.add_argument("--passphrase", help="self-check passphrase (default: generated)")
    p.add_argument("--python-command", dest="python_command", help="python used in the hook commands")
    p.add_argument("--no-hooks", action="store_true", dest="no_hooks")
    p.add_argument("--force", action="store_true", help="replace existing files (old copy is backed up first)")
    p.add_argument("--yes", action="store_true", help="the user agreed to the safety notice")
    args = p.parse_args(argv)
    if args.check:
        return check(args)
    missing = [f"--{n.replace('_', '-')}" for n in ("name", "os", "always_on", "modules") if not getattr(args, n)]
    if missing:
        print(t(args.language, "need", names=", ".join(missing)), file=sys.stderr)
        return 2
    if not args.yes:
        print(t(args.language, "no_consent"), file=sys.stderr)
        return 2
    return install(args)


if __name__ == "__main__":
    raise SystemExit(main())
