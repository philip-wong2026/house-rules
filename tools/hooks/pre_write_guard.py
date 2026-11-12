#!/usr/bin/env python3
"""Claude Code PreToolUse hook: stop careless writes and deletes inside the Space.

Exit 2 = refuse and send stderr back to the model; 0 = allow; 1 = the script itself failed
(allowed, with a note). It only guards against slips. The Bash check is a heuristic, and the
temporary allow file can also be written by the AI, so this is NOT a security boundary.

Rules (paths come from .space/config.json):
  A1 a target that has an unregistered sync-conflict copy beside it (only if uses_sync_drive)
  A2 a sync-conflict copy itself is evidence: do not edit or delete
  A3 history snapshots may only be added to, never overwritten
  A4 protected_paths (credentials, private areas)
  A6 readonly_paths (originals that live next to the Space)
  A7 hook settings and hook scripts (.claude, .space/hooks)
  A8 no new .bak next to originals (use .space/backup.py)
  A9 deletions inside the Space go through .space/recycle.py

Temporary allow (after the user agreed): ~/.house-rules/write-guard/allow.json
  {"entries": [{"path": "private/x.md", "approved_by_user": "<their words>",
                "expires_at": "2026-11-12T15:00:00+08:00"}]}   (at most 10 minutes ahead, with time zone)
Works with Claude Code opened at the Space root; the hook command in .claude/settings.json uses a
relative script path. Windows behaviour is unverified until the GitHub install test has run.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shlex
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common  # noqa: E402
import state_check  # noqa: E402

ROOT = HERE.parents[1]
ALLOW_FILE = Path.home() / ".house-rules" / "write-guard" / "allow.json"
ALLOW_MAX = timedelta(minutes=10)
FIXED_PROTECTED = [(".claude", "A7", "hook settings"), (".space/hooks", "A7", "hook scripts")]
EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

WRITE_HINT = re.compile(r"(?<![<>\d&-])>|\btee\b|\bmv\b|\bcp\b|\brm\b|\brmdir\b|\btouch\b|\bln\b|\bchmod\b|"
                        r"\bchown\b|\brsync\b|\bditto\b|\bsed\s+(-\w+\s+)*-i|\bperl\s+-\w*i|\btruncate\b|write_text|"
                        r"write_bytes|open\([^)]*['\"][wax+]|shutil\.|os\.(remove|rename|replace|unlink)|\.unlink\(|"
                        r"\.rename\(|\.replace\(|\bdel\b|\bmove\b|\bcopy\b|\bRemove-Item\b|\bSet-Content\b|\bOut-File\b",
                        re.I)
DESTRUCTIVE = re.compile(r"(?<![<>\d&-])>(?!>)|\bmv\b|\brm\b|\brmdir\b|\bsed\s+(-\w+\s+)*-i|\bperl\s+-\w*i|"
                         r"\btruncate\b|os\.(remove|rename|replace|unlink)|\.unlink\(|\.rename\(|shutil\.(move|rmtree)|"
                         r"\bdel\b|\bRemove-Item\b", re.I)
BAK = re.compile(r"\.bak(?:[-_.]|$)", re.I)
BAK_TOKEN = re.compile(r"[^\s'\"<>|;&()]*\.bak(?:[-_.][^\s'\"<>|;&()]*)?", re.I)
NOISE = re.compile(r"&>\s*/dev/null|\d?>>?\s*/dev/null|\d>&\d|>\s*\$null|>\s*NUL\b", re.I)
PY_NAME = re.compile(r"python(?:3(?:\.\d+)?)?(?:\.exe)?", re.I)
DELETE_EXES = ("rm", "rmdir", "unlink", "trash", "del", "erase", "rd", "remove-item", "ri")

M = {
    "conflict": ("a sync-conflict copy is evidence, do not edit or delete it: {r}",
                 "同步冲突副本是证据，不改不删：{r}"),
    "history": ("history snapshots may only be added to, never overwritten: {r}",
                "历史快照只可新增、不可覆盖：{r}"),
    "bak": ("do not create .bak files beside originals; use python3 .space/backup.py <file> "
            "(stored in .space/history/write-backups/): {r}",
            "不在正本旁新建 .bak 备份；写前备份用 python3 .space/backup.py <文件>（存 .space/history/write-backups/）：{r}"),
    "bak_cmd": ("do not create .bak files beside originals; use python3 .space/backup.py <file>",
                "不在正本旁新建 .bak 备份；写前备份用 python3 .space/backup.py <文件>"),
    "protected": ("{why}: {r}", "{why}：{r}"),
    "readonly": ("read-only original outside the working scope: {r}", "默认只读的原件：{r}"),
    "a1": ("target has an unregistered or changed conflict copy {c}; compare read-only, keep both sides, then merge",
           "目标旁有未登记或内容已变化的冲突副本 {c}；先只读比对、保全双方再合并"),
    "bash": ("the Bash command looks like a write to {why} (contains '{marker}')",
             "Bash命令疑似写入{why}（含“{marker}”）"),
    "recycle": ("clean up with: python3 .space/recycle.py <path> --reason ... --who claude",
                "清理请用：python3 .space/recycle.py <路径> --reason ... --who claude"),
    "refused": ("[Space guard {rule}] refused: {why}.\nIf this is a false alarm, use the Write/Edit tool (judged by exact "
                "path). If a protected path really must change, get the user's consent first, then add an entry "
                "(path, approved_by_user = their words, expires_at within 10 minutes, with time zone) to {allow} "
                "and retry.",
                "[Space写入前检查 {rule}] 已拒绝：{why}。\n如属误判，改用 Write/Edit 工具（按路径精确判断）；确需写入受保护范围，"
                "先征得用户同意，再在 {allow} 登记 path、approved_by_user（用户原话）、expires_at（≤10分钟、带时区）后重试。"),
    "crashed": ("[Space guard] script error, allowed: {err}", "[Space写入前检查] 脚本出错已放行：{err}"),
}
WHY = {
    "A4": ("protected area", "受保护区域"), "A7": ("hook settings or scripts", "钩子配置或脚本"),
    "A6": ("read-only original", "只读原件"), "A3": ("history snapshot (add only)", "历史快照（只可新增）"),
    "A2": ("conflict copy", "冲突副本"),
}


def _t(cfg, key, **kw):
    return common.tr(M, cfg["language"], key, **kw)


def _why(cfg, key):
    return common.tr(WHY, cfg["language"], key)


def under(rel, prefix):
    prefix = prefix.strip("/")
    return bool(prefix) and (rel == prefix or rel.startswith(prefix + "/"))


def resolve(raw, data):
    p = Path(raw)
    if not p.is_absolute():
        p = Path(data.get("cwd") or os.getcwd()) / p
    return Path(os.path.realpath(p))


def allowed(target, root):
    try:
        entries = json.loads(ALLOW_FILE.read_text(encoding="utf-8"))["entries"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    now = datetime.now(timezone.utc)
    for e in entries:
        try:
            exp = datetime.fromisoformat(str(e["expires_at"]).replace("Z", "+00:00"))
            if exp.utcoffset() is None or not e.get("approved_by_user") or not now < exp <= now + ALLOW_MAX:
                continue
            p = Path(e["path"])
            p = Path(os.path.realpath(p if p.is_absolute() else root / p))
            if target == p or p in target.parents:
                return True
        except (KeyError, ValueError, TypeError):
            continue
    return False


def protected_list(cfg):
    items = [(p, "A4") for p in cfg["protected_paths"]] + [(p, "A6") for p in cfg["readonly_paths"]]
    return items


def _rel(root, p):
    p = Path(p)
    if p.is_absolute():
        try:
            return Path(os.path.realpath(p)).relative_to(root).as_posix()
        except ValueError:
            return None
    return p.as_posix().strip("/")


def check_path(root, target, cfg):
    """(rule, reason) or None."""
    root = Path(os.path.realpath(root))
    try:
        r = target.relative_to(root).as_posix()
    except ValueError:
        for prefix, rule in protected_list(cfg):
            pp = Path(prefix)
            if pp.is_absolute() and (target == pp or pp in target.parents):
                return rule, _t(cfg, "readonly", r=str(target)) if rule == "A6" else \
                    _t(cfg, "protected", why=_why(cfg, rule), r=str(target))
        return None
    if common.is_conflict_name(target.name, cfg["conflict_patterns"]):
        return "A2", _t(cfg, "conflict", r=r)
    if under(r, cfg["history_dir"]) and target.exists():
        return "A3", _t(cfg, "history", r=r)
    for prefix, _, _ in FIXED_PROTECTED:
        if under(r, prefix):
            return "A7", _t(cfg, "protected", why=_why(cfg, "A7"), r=r)
    for prefix, rule in protected_list(cfg):
        rp = _rel(root, prefix)
        if rp and under(r, rp):
            return rule, (_t(cfg, "readonly", r=r) if rule == "A6" else _t(cfg, "protected", why=_why(cfg, rule), r=r))
    if BAK.search(target.name) and not target.exists() and not under(r, cfg["history_dir"]):
        return "A8", _t(cfg, "bak", r=r)
    if cfg["uses_sync_drive"]:
        found, _, _ = state_check.classify(root, cfg)
        for c in found:
            if c["counterpart"] == r:
                return "A1", _t(cfg, "a1", c=c["file"])
    return None


def bash_markers(cfg):
    out = [(".claude/", "A7", False), (".space/hooks", "A7", False)]
    out += [(p.replace("\\", "/").rstrip("/"), "A4", False) for p in cfg["protected_paths"]]
    out += [(p.replace("\\", "/").rstrip("/"), "A6", False) for p in cfg["readonly_paths"]]
    out += [(p, "A2", False) for p in cfg["conflict_patterns"]]
    out.append((cfg["history_dir"], "A3", True))
    return [m for m in out if m[0].strip()]


def check_bash(cmd, cfg):
    code = NOISE.sub(" ", cmd)
    if not WRITE_HINT.search(code):
        return None
    flat = code.replace("\\", "/")
    if re.search(r"\b(cp|mv|ditto|rsync|tee|copy|move)\b|(?<![<>\d&-])>|shutil\.copy|write_", code, re.I) and \
            BAK_TOKEN.search(code) and cfg["history_dir"] not in flat:
        return "A8", _t(cfg, "bak_cmd")
    for marker, rule, destructive_only in bash_markers(cfg):
        if marker in flat and (not destructive_only or DESTRUCTIVE.search(code)):
            return rule, _t(cfg, "bash", why=_why(cfg, rule if rule != "A4" else "A4"), marker=marker)
    return None


def bash_paths(cmd, data):
    return [resolve(t, data) for t in re.findall(r"[^\s'\"<>|;&()]+", cmd) if "/" in t or "\\" in t]


def deletion_in_space(raw, root, cwd, env):
    if raw is None:
        return True
    raw = re.sub(r"\$(?:\{(\w+)\}|(\w+))", lambda m: env.get(m.group(1) or m.group(2), m.group(0)), str(raw))
    if "$" in raw or "`" in raw:
        return True
    expanded = os.path.expanduser(raw) if raw.startswith("~") else raw
    path = Path(os.path.abspath(expanded if Path(expanded).is_absolute() else str(cwd / expanded)))
    real = path.resolve()
    return path == root or root in path.parents or real == root or root in real.parents


def python_deletes(code, root, cwd, env):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return bool(re.search(r"\b(?:remove|unlink|rmdir|rmtree)\s*\(", code))
    aliases, values = {}, {}

    def name(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value) + "." + node.attr
        return ""

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            left, right = value(node.left), value(node.right)
            if left is not None and right is not None:
                return left + right if isinstance(node.op, ast.Add) else str(Path(left) / right)
        if isinstance(node, ast.Call) and name(node.func) in ("Path", "pathlib.Path", "str"):
            return value(node.args[0]) if node.args else "."
        if isinstance(node, ast.Subscript) and name(node.value) == "os.environ":
            return env.get(value(node.slice))
        if isinstance(node, ast.Call) and name(node.func) == "os.getenv" and node.args:
            return env.get(value(node.args[0]))
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                aliases[a.asname or a.name] = (node.module or "") + "." + a.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value(node.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = name(node.func)
        if fn in ("os.remove", "os.unlink", "os.rmdir", "shutil.rmtree"):
            target = value(node.args[0]) if node.args else next(
                (value(k.value) for k in node.keywords if k.arg in ("path", "name")), None)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in ("unlink", "rmdir"):
            target = value(node.func.value)
        else:
            continue
        if deletion_in_space(target, root, cwd, env):
            return True
    return False


def recycle_command(tokens, root, cwd):
    if not tokens or not PY_NAME.fullmatch(Path(tokens[0]).name):
        return False
    args = tokens[1:]
    while args and args[0] in ("-I", "-B", "-u"):
        args = args[1:]
    return bool(args and (cwd / args[0]).resolve() == root / ".space" / "recycle.py")


def check_delete(cmd, root, data):
    """A9: deletions in the Space must go through recycle.py. Heuristic, not a full shell parser."""
    root = root.resolve()
    cwd = Path(data.get("cwd") or root).resolve()
    env = dict(os.environ)
    env.setdefault("TMPDIR", tempfile.gettempdir())
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return "A9" if re.search(r"\b(rm|rmdir|unlink|trash|del|erase|Remove-Item)\b|-delete", cmd, re.I) else None
    chunks, cur = [], []
    for token in tokens:
        if token and all(c in ";&|()\n" for c in token):
            chunks.append(cur)
            cur = []
        else:
            cur.append(token)
    chunks.append(cur)
    uncertain_cd = any(t and all(c in ";&|()\n" for c in t) and ("(" in t or ")" in t or "|" in t) for t in tokens)
    for args in chunks:
        while args and re.match(r"^\w+=", args[0]):
            key, val = args.pop(0).split("=", 1)
            env[key] = val
        while args and Path(args[0]).name in ("command", "exec", "sudo", "env", "xargs"):
            wrapper = Path(args[0]).name
            args = args[1:]
            while args and (args[0].startswith("-") or re.match(r"^\w+=", args[0])):
                takes_arg = (wrapper == "sudo" and args[0] in ("-u", "-g", "-h", "--user", "--group") or
                             wrapper == "xargs" and args[0] in ("-n", "-P", "-I") or
                             wrapper == "env" and args[0] in ("-u", "--unset"))
                args = args[2:] if takes_arg else args[1:]
        if not args:
            continue
        exe = Path(args[0]).name
        if exe == "cd" and len(args) == 2:
            raw = os.path.expandvars(args[1])
            cwd = (cwd / raw).resolve() if "$" not in raw and not uncertain_cd else root
            continue
        if exe in ("bash", "sh", "zsh") and "-c" in args:
            i = args.index("-c")
            if i + 1 < len(args) and check_delete(args[i + 1], root, {**data, "cwd": str(cwd)}):
                return "A9"
        if recycle_command(args, root, cwd):
            continue
        targets = []
        if exe.lower() in DELETE_EXES:
            targets = [x for x in args[1:] if not x.startswith("-") and not re.fullmatch(r"/[A-Za-z]", x)]
            targets = targets or [None]
        elif exe == "find" and ("-delete" in args or any(Path(x).name in DELETE_EXES
                                                       for x in args if "-exec" in args or "-execdir" in args)):
            for x in args[1:]:
                if x.startswith("-") and x not in ("-H", "-L", "-P"):
                    break
                if x not in ("-H", "-L", "-P"):
                    targets.append(x)
            targets = targets or ["."]
            for flag in ("-exec", "-execdir"):
                if flag in args:
                    i = args.index(flag)
                    if i + 1 < len(args) and Path(args[i + 1]).name in DELETE_EXES:
                        targets += [x for x in args[i + 2:] if not x.startswith("-") and x not in ("{}", "+", ";")]
        elif PY_NAME.fullmatch(exe):
            if "-c" in args:
                i = args.index("-c")
                code = args[i + 1] if i + 1 < len(args) else ""
            elif "<<" in args or "<<-" in args:
                code = cmd.split("\n", 1)[1].rsplit("\n", 1)[0] if "\n" in cmd else ""
            else:
                code = ""
            if python_deletes(code, root, cwd, env):
                return "A9"
        if any(deletion_in_space(x, root, cwd, env) for x in targets):
            return "A9"
    return None


def decide(root, data, cfg=None):
    """None (allow) or (rule, reason)."""
    cfg = cfg or common.load_config(root)
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    if tool == "Bash":
        cmd = inp.get("command", "")
        hit = check_bash(cmd, cfg)
        if hit and not any(allowed(p, root) for p in bash_paths(cmd, data)):
            return hit
        if check_delete(cmd, root, data) and not any(allowed(p, root) for p in bash_paths(cmd, data)):
            return "A9", _t(cfg, "recycle")
        return None
    raw = inp.get("file_path") or inp.get("notebook_path")
    if tool not in EDIT_TOOLS or not raw:
        return None
    target = resolve(raw, data)
    hit = check_path(root, target, cfg)
    return None if hit is None or allowed(target, root) else hit


def main(root=ROOT):
    common.stdio_utf8()
    try:
        cfg = common.load_config(root)
        hit = decide(root, json.loads(common.read_stdin_text()), cfg)
    except Exception as exc:  # noqa: BLE001  fail open, with a note
        sys.stderr.write(common.tr(M, "en", "crashed", err=f"{type(exc).__name__}: {exc}") + "\n")
        return 1
    if hit is None:
        return 0
    rule, why = hit
    sys.stderr.write(_t(cfg, "refused", rule=rule, why=why, allow=ALLOW_FILE) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
