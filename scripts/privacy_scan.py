#!/usr/bin/env python3
"""Privacy scan for the Space Open repository. Standard library only. Any hit = exit 1.

  python3 scripts/privacy_scan.py [--root DIR] [--denylist FILE] [--require-denylist] [--no-history] [--json]

What it scans (working tree file CONTENTS and file NAMES, plus git history when a .git exists):
  1. the private denylist: one term per line; '#' comments; 're:<regex>' for a regex; ASCII terms
     match on word boundaries, terms with CJK characters match as substrings; case-insensitive.
     The list is NOT part of the repo. Its path comes from --denylist or the environment variable
     SPACE_OPEN_DENYLIST. Without a list only the generic checks run (use --require-denylist to
     make a missing list an error).
  2. common secret formats (private keys, cloud/API tokens, bot tokens, JWTs, quoted password
     assignments).
  3. personal local paths (/Users/<name>, /home/<name>, C:\\Users\\<name>, /Volumes/...) and
     e-mail addresses other than clearly fake ones (example.com, noreply).
  4. git history: commit messages, author/committer names and e-mails, file names and every diff.
Matched text is never printed in full: hits show file, line, rule and a masked excerpt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ENV_VAR = "SPACE_OPEN_DENYLIST"
MAX_BYTES = 5_000_000
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}

SECRET_RULES = [
    ("private-key", r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    ("aws-access-key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("github-token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    ("api-key-sk", r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),
    ("slack-token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("telegram-bot-token", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("google-api-key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    ("password-assignment", r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"
                            r"\s*[:=]\s*[\"'][A-Za-z0-9/+_.\-!@#$%^&*]{10,}[\"']"),
]
GENERIC_NAMES = {"user", "username", "you", "yourname", "name", "me", "example", "runner", "runneradmin",
                 "alex", "shared", "public", "default", "someone", "foo", "test", "tester"}
PATH_RULES = [
    ("local-path-mac", re.compile(r"/Users/([^/\s'\"<>:]+)")),
    ("local-path-linux", re.compile(r"/home/([^/\s'\"<>:]+)")),
    ("local-path-windows", re.compile(r"(?i)[A-Z]:[\\/]+Users[\\/]+([^\\/\s'\"<>:]+)")),
]
VOLUMES = re.compile(r"/Volumes/[A-Za-z0-9_][^\s'\"<>]*")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
FILE_EXTENSIONS = {"md", "py", "txt", "json", "yml", "yaml", "sh", "js", "html", "css", "png", "jpg", "pdf", "csv", "log"}
FAKE_DOMAINS = ("example.com", "example.org", "example.net", "users.noreply.github.com", "noreply.github.com",
                "localhost", "test.invalid")
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def mask(text):
    text = text.strip()
    return text[:2] + "*" * max(3, len(text) - 2) if len(text) > 2 else "***"


def load_denylist(path):
    rules = []
    for no, raw in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("re:"):
            pattern = re.compile(line[3:], re.I)
        elif CJK.search(line):
            pattern = re.compile(re.escape(line), re.I)
        else:
            pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(line) + r"(?![A-Za-z0-9])", re.I)
        rules.append((f"denylist:{no}", pattern))
    return rules


def scan_text(text, where, deny):
    hits = []
    for no, line in enumerate(text.splitlines() or [""], 1):
        for rule, pat in deny:
            m = pat.search(line)
            if m:
                hits.append({"where": where, "line": no, "rule": rule, "excerpt": mask(m.group(0))})
        for rule, pat in SECRET_RULES:
            m = re.search(pat, line)
            if m:
                hits.append({"where": where, "line": no, "rule": rule, "excerpt": mask(m.group(0))})
        for rule, pat in PATH_RULES:
            for m in pat.finditer(line):
                if m.group(1).lower() not in GENERIC_NAMES and not m.group(1).startswith(("<", "{", "$", "%", "(", "[", "\\")):
                    hits.append({"where": where, "line": no, "rule": rule, "excerpt": mask(m.group(0))})
        for m in VOLUMES.finditer(line):
            hits.append({"where": where, "line": no, "rule": "local-path-volumes", "excerpt": mask(m.group(0))})
        for m in EMAIL.finditer(line):
            domain = m.group(1).lower()
            if domain.rsplit(".", 1)[-1] in FILE_EXTENSIONS:
                continue
            if not any(domain == d or domain.endswith("." + d) for d in FAKE_DOMAINS):
                hits.append({"where": where, "line": no, "rule": "email", "excerpt": mask(m.group(0))})
    return hits


def tree_files(root, skip):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            path = Path(base) / name
            if path.resolve() in skip:
                continue
            yield path


def scan_tree(root, deny, skip):
    hits, scanned = [], 0
    for path in tree_files(root, skip):
        rel = path.relative_to(root).as_posix()
        hits += scan_text(rel, f"name:{rel}", deny)
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        scanned += 1
        if b"\x00" in data[:4096]:
            continue
        hits += scan_text(data.decode("utf-8", errors="replace"), rel, deny)
    return hits, scanned


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, r.stdout


def scan_history(root, deny):
    code, out = git(root, "rev-parse", "--git-dir")
    if code != 0:
        return [], 0
    code, commits = git(root, "rev-list", "--all")
    shas = commits.split() if code == 0 else []
    hits = []
    for sha in shas:
        _, meta = git(root, "show", "-s", "--format=%an%n%ae%n%cn%n%ce%n%B", sha)
        hits += scan_text(meta, f"history:{sha[:10]}:meta", deny)
        _, names = git(root, "show", "--name-only", "--format=", sha)
        hits += scan_text(names, f"history:{sha[:10]}:names", deny)
        _, patch = git(root, "show", "--format=", "--no-color", sha)
        hits += scan_text(patch, f"history:{sha[:10]}:diff", deny)
    code, tags = git(root, "tag", "-l")
    hits += scan_text(tags, "history:tags", deny)
    code, branches = git(root, "branch", "-a", "--format=%(refname:short)")
    hits += scan_text(branches, "history:branches", deny)
    return hits, len(shas)


def run(root, denylist=None, require_denylist=False, history=True):
    root = Path(root).resolve()
    denylist = denylist or os.environ.get(ENV_VAR)
    deny, skip, notes = [], set(), []
    if denylist and Path(denylist).is_file():
        deny = load_denylist(denylist)
        skip.add(Path(denylist).resolve())
        if root in Path(denylist).resolve().parents:
            notes.append("the denylist lives inside the scanned tree; it was skipped, move it out of the repo")
    elif require_denylist:
        return {"ok": False, "error": f"denylist not found (set {ENV_VAR} or pass --denylist)", "hits": []}
    else:
        notes.append(f"no denylist given: only generic checks ran (set {ENV_VAR} to add your private terms)")
    hits, files = scan_tree(root, deny, skip)
    commits = 0
    if history:
        h, commits = scan_history(root, deny)
        hits += h
    return {"ok": not hits, "root": str(root), "files_scanned": files, "commits_scanned": commits,
            "denylist_terms": len(deny), "hit_count": len(hits), "hits": hits, "notes": notes}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    p.add_argument("--denylist")
    p.add_argument("--require-denylist", action="store_true")
    p.add_argument("--no-history", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    result = run(a.root, a.denylist, a.require_denylist, not a.no_history)
    if a.json or not result.get("ok"):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"privacy scan OK: {result['files_scanned']} files, {result['commits_scanned']} commits, "
              f"{result['denylist_terms']} denylist terms, 0 hits")
        for n in result["notes"]:
            print("note:", n)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
