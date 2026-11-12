"""Normal and error cases for every tool, run the way a user runs them (as installed in a Space)."""
import datetime as dt
import hashlib
import json
import os
import time
import unittest
from pathlib import Path

from helpers import SpaceCase, run


class BackupTests(SpaceCase):
    def test_backup_copies_file_with_timestamp(self):
        note = self.write("work/note.md", "hello\n")
        r = run(self.space, "backup.py", "work/note.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        found = list((self.space / ".space" / "history" / "write-backups").rglob("note@*.md"))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].read_text(encoding="utf-8"), note.read_text(encoding="utf-8"))

    def test_backup_twice_never_overwrites(self):
        self.write("work/note.md", "hello\n")
        run(self.space, "backup.py", "work/note.md")
        run(self.space, "backup.py", "work/note.md")
        found = list((self.space / ".space" / "history" / "write-backups").rglob("note@*.md"))
        self.assertEqual(len(found), 2)

    def test_backup_missing_file_fails(self):
        r = run(self.space, "backup.py", "work/nope.md")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Not a file", r.stderr)

    def test_backup_without_arguments_prints_usage(self):
        r = run(self.space, "backup.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Back up a file", r.stdout)


class RecycleTests(SpaceCase):
    def recycle(self, *paths, reason="test", who="tester", extra=()):
        return run(self.space, "recycle.py", *paths, "--reason", reason, "--who", who, *extra)

    def test_move_and_restore_round_trip(self):
        self.write("work/old.md", "keep me\n")
        r = self.recycle("work/old.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.space / "work" / "old.md").exists())
        binned = [p for p in (self.space / ".space" / "recycle-bin").rglob("old.md")]
        self.assertEqual(len(binned), 1)
        rel = binned[0].relative_to(self.space).as_posix()
        r2 = run(self.space, "recycle.py", "--restore", rel)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual((self.space / "work" / "old.md").read_text(encoding="utf-8"), "keep me\n")

    def test_dry_run_moves_nothing(self):
        self.write("work/old.md", "x\n")
        r = self.recycle("work/old.md", extra=("--dry-run",))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.space / "work" / "old.md").exists())

    def test_refuses_protected_names_and_rule_files(self):
        self.write("work/original-contract.md", "x\n")
        for target in ["work/original-contract.md", "AGENTS.md", "STATE.md", "work"]:
            r = self.recycle(target)
            self.assertEqual(r.returncode, 2, target)
        self.assertTrue((self.space / "AGENTS.md").exists())

    def test_refuses_secret_suffix_and_outside_path(self):
        self.write("work/key.pem", "x\n")
        self.assertEqual(self.recycle("work/key.pem").returncode, 2)
        outside = self.space.parent / "outside.md"
        outside.write_text("x\n", encoding="utf-8")
        self.assertEqual(self.recycle(str(outside)).returncode, 2)
        self.assertTrue(outside.exists())

    def test_requires_reason_and_who(self):
        self.write("work/old.md", "x\n")
        r = run(self.space, "recycle.py", "work/old.md")
        self.assertEqual(r.returncode, 2)
        self.assertTrue((self.space / "work" / "old.md").exists())

    def test_restore_refuses_when_original_exists(self):
        self.write("work/old.md", "v1\n")
        self.recycle("work/old.md")
        self.write("work/old.md", "v2\n")
        binned = next((self.space / ".space" / "recycle-bin").rglob("old.md"))
        r = run(self.space, "recycle.py", "--restore", binned.relative_to(self.space).as_posix())
        self.assertEqual(r.returncode, 2)
        self.assertEqual((self.space / "work" / "old.md").read_text(encoding="utf-8"), "v2\n")

    def test_symlink_is_refused(self):
        real = self.write("work/real.md", "x\n")
        link = self.space / "work" / "link.md"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        self.assertEqual(self.recycle("work/link.md").returncode, 2)

    def test_empty_removes_only_expired_recorded_day_folders(self):
        import recycle
        self.write("work/old.md", "x\n")
        long_ago = dt.datetime.now().astimezone() - dt.timedelta(days=45)
        recycle.Run(self.space, now=long_ago, who="t", reason="t").move(["work/old.md"])
        self.write("work/new.md", "y\n")
        self.recycle("work/new.md")
        r = run(self.space, "recycle.py", "--empty")
        self.assertEqual(r.returncode, 0, r.stderr)
        days = sorted(p.name for p in (self.space / ".space" / "recycle-bin").iterdir() if p.is_dir())
        self.assertEqual(days, [dt.date.today().isoformat()])
        self.assertTrue(list((self.space / ".space" / "recycle-bin").rglob("new.md")))

    def test_empty_keeps_old_folder_that_holds_unrecorded_files(self):
        import recycle
        long_ago = dt.datetime.now().astimezone() - dt.timedelta(days=45)
        self.write("work/old.md", "x\n")
        recycle.Run(self.space, now=long_ago, who="t", reason="t").move(["work/old.md"])
        day = next(p for p in (self.space / ".space" / "recycle-bin").iterdir() if p.is_dir())
        (day / "stranger.md").write_text("not in the record\n", encoding="utf-8")
        run(self.space, "recycle.py", "--empty")
        self.assertTrue(day.exists())
        self.assertTrue((day / "stranger.md").exists())


class ReadRulesTests(SpaceCase):
    def test_manifest_lists_required_files(self):
        r = run(self.space, "read_rules.py", "manifest")
        self.assertEqual(r.returncode, 0, r.stderr)
        names = [f["file"] for f in json.loads(r.stdout)["required"]]
        self.assertEqual(names, ["AGENTS.md", "CLAUDE.md", "STATE.md", "PRINCIPLES.md"])

    def test_read_part_matches_sha(self):
        r = run(self.space, "read_rules.py", "read", "AGENTS.md", "--part", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("BEGIN {"))
        head = json.loads(r.stdout.splitlines()[0][len("BEGIN "):])
        body = (self.space / "AGENTS.md").read_bytes()
        self.assertEqual(head["sha256"], hashlib.sha256(body).hexdigest())

    def test_missing_required_file_stops(self):
        (self.space / "PRINCIPLES.md").unlink()
        r = run(self.space, "read_rules.py", "manifest")
        self.assertEqual(r.returncode, 2)
        self.assertIn("stop the task", r.stderr)

    def test_empty_required_file_stops(self):
        self.write("PRINCIPLES.md", "  \n")
        self.assertEqual(run(self.space, "read_rules.py", "manifest").returncode, 2)

    def test_refuses_outside_part_range_and_non_markdown(self):
        for args in (["read", "../x.md", "--part", "1"], ["read", ".space/config.json", "--part", "1"],
                     ["read", "AGENTS.md", "--part", "99"], ["read", "AGENTS.md", "--part", "1",
                                                              "--expected-sha", "0" * 64]):
            self.assertEqual(run(self.space, "read_rules.py", *args).returncode, 2, args)


class RedactTests(SpaceCase):
    def setUp(self):
        super().setUp()
        import redact
        self.redact = redact

    def test_flags_each_category(self):
        samples = {"credential": "my password is abc", "health": "blood pressure 150",
                   "money": "salary is $5000", "id-or-account": "card no 6222 0212 3456 7890",
                   "address": "home address: 5 Main street"}
        for category, text in samples.items():
            self.assertIn(category, self.redact.find(text), text)

    def test_chinese_keywords(self):
        self.assertIn("health", self.redact.find("今天去医院复查"))
        self.assertIn("credential", self.redact.find("银行密码是"))

    def test_plain_text_and_dates_pass(self):
        for text in ["Plan the garden project", "task 20261112-0001 due 2026-11-19", "项目周会纪要"]:
            self.assertEqual(self.redact.find(text), [], text)

    def test_mask_replaces_text_and_keeps_clean_text(self):
        masked = self.redact.mask("my password is abc", "note 3")
        self.assertNotIn("abc", masked)
        self.assertIn("note 3", masked)
        self.assertEqual(self.redact.mask("hello", "x"), "hello")
        self.assertIn("原话", self.redact.mask("my password is abc", "x", lang="zh-CN"))

    def test_extra_rules_from_config(self):
        compiled = self.redact.compile_rules([{"name": "project-code", "pattern": r"ACME-\d+"}])
        self.assertEqual(self.redact.find("see ACME-42", compiled), ["project-code"])


class SharedWriteTests(SpaceCase):
    def sw(self, *args):
        r = run(self.space, "shared_write.py", *args)
        return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else {})

    def candidate(self, text):
        path = self.space.parent / "candidate.txt"
        path.write_bytes(text.encode("utf-8"))
        return str(path)

    def test_read_then_write_with_matching_sha(self):
        code, info = self.sw("read", "STATE.md")
        self.assertEqual(code, 0)
        self.assertIn("budget", info)
        text = info["text"] + "\n- new line\n"
        code, out = self.sw("write", "STATE.md", "--expected", info["sha256"], "--candidate", self.candidate(text))
        self.assertEqual(code, 0, out)
        self.assertEqual((self.space / "STATE.md").read_text(encoding="utf-8"), text)

    def test_stale_sha_exits_75_and_keeps_file(self):
        before = (self.space / "STATE.md").read_text(encoding="utf-8")
        code, out = self.sw("write", "STATE.md", "--expected", "0" * 64, "--candidate", self.candidate("X\n"))
        self.assertEqual(code, 75)
        self.assertFalse(out["ok"])
        self.assertEqual((self.space / "STATE.md").read_text(encoding="utf-8"), before)

    def test_not_shared_or_outside_is_rejected(self):
        for target in ["work/README.md", "../x.md", "/etc/passwd"]:
            code, _ = self.sw("read", target)
            self.assertEqual(code, 75, target)

    def test_over_budget_candidate_is_refused(self):
        _, info = self.sw("read", "STATE.md")
        code, out = self.sw("write", "STATE.md", "--expected", info["sha256"],
                            "--candidate", self.candidate("x" * 5000))
        self.assertEqual(code, 75)
        self.assertIn("STATE_BUDGET_EXCEEDED", out["error"])

    def test_missing_arguments(self):
        code, _ = self.sw("write", "STATE.md")
        self.assertEqual(code, 75)

    def test_new_file_needs_null_sha(self):
        self.config(shared_files=["STATE.md", "work/shared.md"])
        code, _ = self.sw("write", "work/shared.md", "--expected", "null", "--candidate", self.candidate("a\n"))
        self.assertEqual(code, 0)
        code, _ = self.sw("write", "work/shared.md", "--expected", "null", "--candidate", self.candidate("b\n"))
        self.assertEqual(code, 75)


class DateCopyTests(SpaceCase):
    KEY = [{"item": "Launch", "keywords": "launch", "sources": ["work/README.md"]}]

    def test_no_key_dates_means_clean(self):
        r = run(self.space, "date_copy_check.py")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(json.loads(r.stdout)["ok"])

    def test_copy_in_other_file_is_found(self):
        self.config(key_dates=self.KEY)
        self.write("work/README.md", "# Work\n\nLaunch is on 2026-12-01.\n")
        self.write("STATE.md", "# State\n\nLaunch 2026-12-01.\n- [work](work/STATE.md)\n- [personal](personal/STATE.md)\n")
        r = run(self.space, "date_copy_check.py")
        self.assertEqual(r.returncode, 1)
        files = {h["file"] for h in json.loads(r.stdout)["details"]}
        self.assertEqual(files, {"STATE.md"})

    def test_correction_marks_and_source_are_ignored(self):
        self.config(key_dates=self.KEY)
        self.write("work/README.md", "Launch is on 2026-12-01.\n")
        self.write("work/STATE.md", "Launch ~~2026-11-30~~ superseded\n")
        self.assertEqual(run(self.space, "date_copy_check.py").returncode, 0)


class RecordCheckTests(SpaceCase):
    def project(self, status_date):
        self.write("work/proj/notes.md", "work\n")
        self.write("work/proj/README.md", f"# Proj\n\n## Current status\n\n- {status_date} started\n")
        self.config(record_check={"grace_days": 2, "projects": [
            {"name": "Proj", "folder": "work/proj", "state": "work/STATE.md", "key": "Proj"}]})

    def test_up_to_date_project_is_ok(self):
        self.project(dt.date.today().isoformat())
        r = run(self.space, "record_check.py", "--json")
        self.assertEqual(json.loads(r.stdout)[0]["status"], "ok")

    def test_stale_status_is_named(self):
        old = (dt.date.today() - dt.timedelta(days=10)).isoformat()
        self.project(old)
        rows = json.loads(run(self.space, "record_check.py", "--json").stdout)
        self.assertEqual(rows[0]["status"], "stale")
        self.assertGreaterEqual(rows[0]["gap_days"], 10)
        self.assertIn("days behind", run(self.space, "record_check.py").stdout)

    def test_missing_folder_and_missing_entry(self):
        self.config(record_check={"grace_days": 2, "projects": [
            {"name": "Ghost", "folder": "work/ghost", "state": "work/STATE.md", "key": "Ghost"}]})
        self.assertEqual(json.loads(run(self.space, "record_check.py", "--json").stdout)[0]["status"],
                         "folder_missing")
        self.write("work/other/a.md", "x\n")
        self.config(record_check={"grace_days": 2, "projects": [
            {"name": "Other", "folder": "work/other", "state": "work/STATE.md", "key": "ZZZ-not-there"}]})
        self.assertEqual(json.loads(run(self.space, "record_check.py", "--json").stdout)[0]["status"], "missing")

    def test_future_date_is_a_plan_not_a_record(self):
        future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        self.project(future)
        self.assertEqual(json.loads(run(self.space, "record_check.py", "--json").stdout)[0]["status"], "no_date")


class StateCheckTests(SpaceCase):
    def check(self):
        r = run(self.space, "state_check.py")
        return r.returncode, json.loads(r.stdout)

    def test_fresh_install_is_ok_with_backup_warning(self):
        code, res = self.check()
        self.assertEqual(code, 0, res)
        self.assertTrue(any("backup" in w.lower() for w in res["warnings"]))

    def test_backup_done_removes_warning(self):
        self.config(backup={"status": "done", "method": "external drive"})
        _, res = self.check()
        self.assertEqual(res["warnings"], [])

    def test_oversized_state_is_error(self):
        self.write("work/STATE.md", "# Work\n\n" + "x" * 7000 + "\n")
        code, res = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("work/STATE.md" in e for e in res["errors"]))

    def test_broken_link_and_dated_heading_are_errors(self):
        text = (self.space / "STATE.md").read_text(encoding="utf-8")
        self.write("STATE.md", text + "\n[gone](nowhere.md)\n\n## 2026-11-01 diary\n")
        code, res = self.check()
        self.assertEqual(code, 1)
        joined = " ".join(res["errors"])
        self.assertIn("nowhere.md", joined)

    def test_missing_required_file_is_error(self):
        (self.space / "PRINCIPLES.md").unlink()
        code, res = self.check()
        self.assertEqual(code, 1)

    def test_stray_bak_is_warned(self):
        self.write("work/a.md.bak", "x\n")
        _, res = self.check()
        self.assertTrue(any(".bak" in w or "backup copy" in w for w in res["warnings"]), res["warnings"])

    def test_sync_conflict_copy_found_only_when_sync_drive_used(self):
        self.write("work/a-NSConflict.md", "x\n")
        _, res = self.check()
        self.assertEqual(res["conflicts"], [])
        self.config(uses_sync_drive=True)
        _, res = self.check()
        self.assertEqual(len(res["conflicts"]), 1)

    def test_oversized_record_is_error(self):
        self.config(record_dirs=["work/records"])
        self.write("work/records/big.txt", "line\n" * 400)
        code, res = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(len(res["oversized_records"]), 1)


def hook(space, script, payload, env=None):
    import subprocess
    import sys
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, str(Path(space) / ".space" / "hooks" / script)],
                          input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                          cwd=str(space), env=e, timeout=60)


class WriteGuardTests(SpaceCase):
    def write_payload(self, rel, tool="Write"):
        return {"tool_name": tool, "tool_input": {"file_path": str(self.space / rel)}, "cwd": str(self.space)}

    def bash(self, cmd):
        return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(self.space)}

    def test_normal_note_is_allowed(self):
        self.assertEqual(hook(self.space, "pre_write_guard.py", self.write_payload("work/new.md")).returncode, 0)

    def test_hook_folder_and_settings_are_refused(self):
        for rel in [".space/hooks/pre_write_guard.py", ".claude/settings.json"]:
            r = hook(self.space, "pre_write_guard.py", self.write_payload(rel, "Edit"))
            self.assertEqual(r.returncode, 2, rel)
            self.assertIn("A7", r.stderr)

    def test_protected_and_readonly_paths(self):
        self.config(protected_paths=["private"], readonly_paths=["originals"])
        self.assertEqual(hook(self.space, "pre_write_guard.py", self.write_payload("private/x.md")).returncode, 2)
        self.assertEqual(hook(self.space, "pre_write_guard.py", self.write_payload("originals/x.md")).returncode, 2)
        self.assertEqual(hook(self.space, "pre_write_guard.py", self.write_payload("work/x.md")).returncode, 0)

    def test_history_is_add_only(self):
        self.write(".space/history/write-backups/2026-11-01/a@010101.md", "x\n")
        r = hook(self.space, "pre_write_guard.py", self.write_payload(".space/history/write-backups/2026-11-01/a@010101.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("A3", r.stderr)
        r = hook(self.space, "pre_write_guard.py", self.write_payload(".space/history/write-backups/2026-11-01/new.md"))
        self.assertEqual(r.returncode, 0)

    def test_new_bak_is_refused(self):
        r = hook(self.space, "pre_write_guard.py", self.write_payload("work/a.md.bak"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("A8", r.stderr)

    def test_bash_delete_must_use_recycle(self):
        self.write("work/a.md", "x\n")
        r = hook(self.space, "pre_write_guard.py", self.bash("rm work/a.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("A9", r.stderr)
        r = hook(self.space, "pre_write_guard.py", self.bash("ls work"))
        self.assertEqual(r.returncode, 0)

    def test_bash_touching_hook_folder_is_refused(self):
        r = hook(self.space, "pre_write_guard.py", self.bash("echo x > .space/hooks/pre_write_guard.py"))
        self.assertEqual(r.returncode, 2)

    def test_garbage_input_fails_open_with_note(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(self.space / ".space" / "hooks" / "pre_write_guard.py")],
                           input="not json", capture_output=True, text=True, cwd=str(self.space))
        self.assertEqual(r.returncode, 1)
        self.assertIn("script error", r.stderr.lower())

    def test_temporary_allow_requires_approval_and_expiry(self):
        home = self.space.parent / "home"
        env = {"HOME": str(home), "USERPROFILE": str(home)}
        self.config(protected_paths=["private"])
        allow = home / ".space-open" / "write-guard" / "allow.json"
        allow.parent.mkdir(parents=True)
        soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).isoformat()
        late = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).isoformat()
        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()
        payload = self.write_payload("private/x.md")
        cases = [({"path": "private", "approved_by_user": "yes, go", "expires_at": soon}, 0),
                 ({"path": "private", "approved_by_user": "", "expires_at": soon}, 2),
                 ({"path": "private", "approved_by_user": "yes", "expires_at": late}, 2),
                 ({"path": "private", "approved_by_user": "yes", "expires_at": past}, 2),
                 ({"path": "private", "approved_by_user": "yes", "expires_at": "2099-01-01T00:00:00"}, 2)]
        for entry, expected in cases:
            allow.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
            r = hook(self.space, "pre_write_guard.py", payload, env)
            self.assertEqual(r.returncode, expected, entry)


class TurnCheckTests(SpaceCase):
    def test_silent_when_clean(self):
        self.config(backup={"status": "done", "method": "x"})
        r = hook(self.space, "turn_check.py", {"hook_event_name": "UserPromptSubmit"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")

    def test_prints_notice_for_errors_and_warnings(self):
        (self.space / "PRINCIPLES.md").unlink()
        r = hook(self.space, "turn_check.py", {"hook_event_name": "UserPromptSubmit"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("turn check", r.stdout)
        self.assertIn("PRINCIPLES.md", r.stdout)
        self.assertIn("backup", r.stdout.lower())

    def test_never_blocks_on_bad_input(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(self.space / ".space" / "hooks" / "turn_check.py")],
                           input="}{", capture_output=True, text=True, cwd=str(self.space))
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
