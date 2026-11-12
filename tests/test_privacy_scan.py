"""Tests for scripts/privacy_scan.py. Fake secrets and private-looking paths are built at run time,
so this file itself contains nothing the scan would flag."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import REPO

sys.path.insert(0, str(REPO / "scripts"))
import privacy_scan  # noqa: E402

SCRIPT = REPO / "scripts" / "privacy_scan.py"


def fake_secrets():
    return {
        "private-key": "-----BEGIN " + "RSA PRIVATE KEY-----",
        "aws-access-key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "github-token": "gh" + "p_" + "a1B2c3D4e5" * 4,
        "api-key-sk": "sk" + "-" + "abcdefghij0123456789ABCD",
        "telegram-bot-token": "123456789" + ":" + "AAH" + "x" * 32,
        "password-assignment": 'pass' + 'word = "' + "Abcdef1234!x" + '"',
    }


def mac_path(name):
    return "/Use" + "rs/" + name + "/notes"


class Tree(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve() / "repo"
        self.root.mkdir()
        self.deny = Path(self._tmp.name).resolve() / "deny.txt"

    def put(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def scan(self, terms=None, **kw):
        if terms is not None:
            self.deny.write_text("\n".join(terms) + "\n", encoding="utf-8")
            kw["denylist"] = str(self.deny)
        return privacy_scan.run(self.root, **kw)

    def rules(self, result):
        return {h["rule"] for h in result["hits"]}


class CleanTree(Tree):
    def test_clean_tree_passes(self):
        self.put("README.md", "Hello, this is a Space.\nSee https://example.com/a and me@example.com\n")
        self.put("a/b.py", "x = 1\n")
        res = self.scan(["zebrapersonxyz"])
        self.assertTrue(res["ok"], res["hits"])
        self.assertEqual(res["denylist_terms"], 1)

    def test_generic_example_paths_are_allowed(self):
        self.put("doc.md", "Install into /Users/<you>/Space or /home/user/Space or C:\\Users\\You\\Space\n")
        self.assertTrue(self.scan()["ok"])

    def test_git_internal_and_pycache_are_skipped(self):
        self.put(".git/config", "email = " + "me@" + "corp.test.org\n")
        self.put("__pycache__/x.pyc", "me@" + "corp.test.org")
        self.assertTrue(self.scan()["ok"])


class SecretFormats(Tree):
    def test_every_secret_format_is_flagged(self):
        for rule, text in fake_secrets().items():
            self.put("f.txt", text + "\n")
            res = self.scan()
            self.assertIn(rule, self.rules(res), rule)
            self.assertFalse(res["ok"])

    def test_matched_text_is_masked_in_output(self):
        secret = fake_secrets()["github-token"]
        self.put("f.txt", secret + "\n")
        out = json.dumps(self.scan())
        self.assertNotIn(secret, out)
        self.assertNotIn(secret[:12], out)

    def test_local_paths_and_real_emails_are_flagged(self):
        self.put("a.md", "see " + mac_path("someoneelse") + "\n")
        self.put("b.md", "write to " + "pers" + "on@" + "corp.test.org" + "\n")
        self.put("c.md", "/Volumes/" + "Disk/stuff\n")
        rules = self.rules(self.scan())
        self.assertTrue({"local-path-mac", "email", "local-path-volumes"} <= rules, rules)

    def test_backup_style_file_names_are_not_emails(self):
        self.put("history/note@111734.md", "see history/note@111734.md and a@010101.md\n")
        self.assertTrue(self.scan()["ok"])

    def test_file_names_are_scanned_too(self):
        self.put("notes-zebrapersonxyz.md", "clean\n")
        res = self.scan(["zebrapersonxyz"])
        self.assertFalse(res["ok"])
        self.assertTrue(res["hits"][0]["where"].startswith("name:"))


class Denylist(Tree):
    def test_ascii_term_uses_word_boundaries(self):
        self.put("a.md", "plain words, Ann's list\n")
        self.assertFalse(self.scan(["ann"])["ok"])
        self.put("a.md", "annual planning and channel\n")
        self.assertTrue(self.scan(["ann"])["ok"])

    def test_cjk_term_matches_inside_text(self):
        self.put("a.md", "这里有王小明同学的名字\n")
        self.assertFalse(self.scan(["王小明"])["ok"])
        self.put("a.md", "这里什么也没有\n")
        self.assertTrue(self.scan(["王小明"])["ok"])

    def test_regex_term_comments_and_case(self):
        self.put("a.md", "Order ZEBRA-1234 shipped\n")
        self.assertFalse(self.scan(["# comment", "", r"re:zebra-\d+"])["ok"])
        self.assertFalse(self.scan(["zebra"])["ok"])

    def test_denylist_inside_repo_is_skipped_with_note(self):
        inside = self.root / "deny.txt"
        inside.write_text("zebrapersonxyz\n", encoding="utf-8")
        res = privacy_scan.run(self.root, denylist=str(inside))
        self.assertTrue(res["ok"])
        self.assertTrue(any("inside the scanned tree" in n for n in res["notes"]))

    def test_missing_denylist(self):
        self.put("a.md", "x\n")
        res = privacy_scan.run(self.root, denylist=str(self.root / "nope.txt"))
        self.assertTrue(res["ok"])
        self.assertTrue(any("no denylist" in n for n in res["notes"]))
        strict = privacy_scan.run(self.root, denylist=str(self.root / "nope.txt"), require_denylist=True)
        self.assertFalse(strict["ok"])
        self.assertIn("denylist not found", strict["error"])


class History(Tree):
    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="Test Author", GIT_AUTHOR_EMAIL="author@example.com",
                   GIT_COMMITTER_NAME="Test Author", GIT_COMMITTER_EMAIL="author@example.com")
        r = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def setUp(self):
        super().setUp()
        if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
            self.skipTest("git not available")
        self.git("init", "-q")

    def test_secret_removed_from_tree_but_still_in_history_is_found(self):
        secret = fake_secrets()["aws-access-key"]
        self.put("a.txt", "key " + secret + "\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "add")
        self.put("a.txt", "clean now\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "remove")
        self.assertTrue(self.scan(history=False)["ok"])
        res = self.scan()
        self.assertFalse(res["ok"])
        self.assertTrue(any(h["where"].startswith("history:") for h in res["hits"]))
        self.assertEqual(res["commits_scanned"], 2)

    def test_commit_message_and_author_are_scanned(self):
        self.put("a.txt", "clean\n")
        self.git("add", "-A")
        env_cmd = ["-c", "user.name=Zebraperson Xyz", "-c", "user.email=a@example.com",
                   "commit", "-q", "-m", "note by zebrapersonxyz"]
        self.git(*env_cmd)
        res = self.scan(["zebrapersonxyz"])
        self.assertFalse(res["ok"])
        self.assertTrue(all("meta" in h["where"] or "names" in h["where"] for h in res["hits"]))

    def test_clean_history_passes(self):
        self.put("a.txt", "clean\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "first")
        res = self.scan(["zebrapersonxyz"])
        self.assertTrue(res["ok"], res["hits"])
        self.assertEqual(res["commits_scanned"], 1)


class CommandLine(Tree):
    def cli(self, *args, env=None):
        e = dict(os.environ)
        e.pop("SPACE_OPEN_DENYLIST", None)
        e.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", env=e)

    def test_exit_codes(self):
        self.put("a.md", "fine\n")
        r = self.cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("privacy scan OK", r.stdout)
        self.put("b.md", fake_secrets()["github-token"] + "\n")
        r = self.cli()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["ok"], False)

    def test_denylist_from_environment_variable(self):
        self.put("a.md", "mentions zebrapersonxyz here\n")
        self.deny.write_text("zebrapersonxyz\n", encoding="utf-8")
        self.assertEqual(self.cli(env={"SPACE_OPEN_DENYLIST": str(self.deny)}).returncode, 1)
        self.assertEqual(self.cli().returncode, 0)

    def test_require_denylist_fails_without_one(self):
        self.put("a.md", "fine\n")
        r = self.cli("--require-denylist")
        self.assertEqual(r.returncode, 1)
        self.assertIn("denylist not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
