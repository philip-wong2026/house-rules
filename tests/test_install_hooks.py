import contextlib
import io
import json
import os
import subprocess
import sys
import unittest

from helpers import SpaceCase, setup_mod


def hook(space, script, payload, event_cwd=None):
    return subprocess.run([sys.executable, str(space / ".space" / "hooks" / script)],
                          input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                          cwd=str(event_cwd or space), timeout=60)


def tool(space, *argv):
    return subprocess.run([sys.executable, str(space / ".space" / argv[0]), *argv[1:]], capture_output=True,
                          text=True, encoding="utf-8", cwd=str(space), timeout=60)


class InstallHooksTests(SpaceCase):
    def norm(self, path):
        return str(path).replace("\\", "/")

    def settings(self, folder=""):
        p = self.space / folder / ".claude" / "settings.json" if folder else self.space / ".claude" / "settings.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_every_top_level_folder_gets_absolute_hooks(self):
        for folder in ["", "work", "personal"]:
            cmds = [h["command"] for g in self.settings(folder)["hooks"]["PreToolUse"] for h in g["hooks"]]
            self.assertEqual(len(cmds), 1, folder)
            self.assertIn(self.norm(self.space / ".space" / "hooks" / "pre_write_guard.py"), cmds[0])

    def test_installed_tool_finds_new_folder_and_refreshes(self):
        (self.space / "projects").mkdir()
        r = tool(self.space, "state_check.py")
        self.assertIn("projects", r.stdout)  # warning names the unguarded folder
        r = tool(self.space, "install_hooks.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["missing"], [])
        self.assertTrue((self.space / "projects" / ".claude" / "settings.json").is_file())
        again = json.loads(tool(self.space, "install_hooks.py").stdout)
        self.assertTrue(all(f["result"] == "unchanged" for f in again["files"]))

    def test_old_relative_command_is_refreshed_not_duplicated(self):
        p = self.space / ".claude" / "settings.json"
        data = self.settings()
        data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "python3 .space/hooks/pre_write_guard.py"
        p.write_text(json.dumps(data), encoding="utf-8")
        tool(self.space, "install_hooks.py")
        cmds = [h["command"] for g in self.settings()["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(len(cmds), 1)
        self.assertIn(self.norm(self.space), cmds[0])

    def test_guard_runs_from_a_module_folder_and_protects_module_claude(self):
        work = self.space / "work"
        payload = {"tool_name": "Write", "cwd": str(work),
                   "tool_input": {"file_path": str(work / ".claude" / "settings.json")}}
        r = hook(self.space, "pre_write_guard.py", payload, event_cwd=work)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("A7", r.stderr)
        ok = {"tool_name": "Write", "cwd": str(work), "tool_input": {"file_path": str(work / "note.md")}}
        self.assertEqual(hook(self.space, "pre_write_guard.py", ok, event_cwd=work).returncode, 0)

    def test_refusal_tail_depends_on_rule(self):
        bak = {"tool_name": "Write", "cwd": str(self.space), "tool_input": {"file_path": str(self.space / "work" / "a.md.bak")}}
        r = hook(self.space, "pre_write_guard.py", bak)
        self.assertIn("A8", r.stderr)
        self.assertNotIn("allow.json", r.stderr)
        self.assertNotIn("Write/Edit", r.stderr)
        a7 = {"tool_name": "Write", "cwd": str(self.space), "tool_input": {"file_path": str(self.space / ".claude" / "settings.json")}}
        r = hook(self.space, "pre_write_guard.py", a7)
        self.assertIn("allow.json", r.stderr)
        self.assertNotIn("Write/Edit", r.stderr)
        self.write("work/x.md", "x\n")
        rm = {"tool_name": "Bash", "cwd": str(self.space), "tool_input": {"command": "rm work/x.md"}}
        r = hook(self.space, "pre_write_guard.py", rm)
        self.assertIn("A9", r.stderr)
        self.assertNotIn("allow.json", r.stderr)
        sh = {"tool_name": "Bash", "cwd": str(self.space), "tool_input": {"command": "echo x > .claude/settings.json"}}
        r = hook(self.space, "pre_write_guard.py", sh)
        self.assertIn("Write/Edit", r.stderr)
        self.assertIn("allow.json", r.stderr)

    def test_self_check_reports_warnings_and_missing_hooks(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_mod.main(["--check", "--target", str(self.space)])
        res = json.loads(out.getvalue())
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(len(res["warnings"]), 2)  # backup pending + no protected folder
        (self.space / "notes").mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_mod.main(["--check", "--target", str(self.space)])
        self.assertEqual(code, 1)
        self.assertIn("notes", out.getvalue())

    def test_session_start_reminds_when_nothing_is_protected(self):
        r = hook(self.space, "turn_check.py", {"hook_event_name": "SessionStart"})
        self.assertIn("protected_paths", r.stdout)
        r = hook(self.space, "turn_check.py", {"hook_event_name": "UserPromptSubmit"})
        self.assertNotIn("protected_paths", r.stdout)


if __name__ == "__main__":
    unittest.main()
