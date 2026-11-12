import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from helpers import REPO, SpaceCase, install, run, setup_mod

TEMPLATE_NAMES = ["AGENTS.md", "CLAUDE.md", "PRINCIPLES.md", "STATE.md", "MODULE-STATE.md", "MODULE-README.md",
                  "BACKUP.md", "state-maintenance.md", "project-three-rules.md", "agent-customization.md"]


class TemplatesExist(unittest.TestCase):
    def test_every_template_exists_in_both_languages(self):
        for lang in ("en", "zh-CN"):
            for name in TEMPLATE_NAMES:
                self.assertTrue((REPO / "templates" / lang / name).is_file(), f"{lang}/{name}")

    def test_both_languages_use_the_same_placeholders(self):
        import re
        pat = re.compile(r"\{\{(\w+)\}\}")
        for name in TEMPLATE_NAMES:
            en = set(pat.findall((REPO / "templates" / "en" / name).read_text(encoding="utf-8")))
            zh = set(pat.findall((REPO / "templates" / "zh-CN" / name).read_text(encoding="utf-8")))
            self.assertEqual(en, zh, name)


class InstallEnglish(SpaceCase):
    def test_generated_files_exist_and_have_no_placeholder_left(self):
        for rel in ["AGENTS.md", "CLAUDE.md", "PRINCIPLES.md", "STATE.md", "BACKUP.md", "work/STATE.md",
                    "personal/README.md", ".space/config.json", ".space/state_check.py",
                    ".space/hooks/pre_write_guard.py", ".space/project-three-rules.md",
                    ".space/agent-customization.md", ".space/state-maintenance.md", ".claude/settings.json"]:
            path = self.space / rel
            self.assertTrue(path.is_file(), rel)
            self.assertNotIn("{{", path.read_text(encoding="utf-8"), rel)

    def test_base_card_has_passphrase_and_user_name(self):
        card = (self.space / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertRegex(card, r"Self-check passphrase: \S+")
        self.assertIn("Alex", card)

    def test_principles_template_is_empty_of_opinions(self):
        text = (self.space / "PRINCIPLES.md").read_text(encoding="utf-8")
        self.assertIn("intentionally empty", text)
        self.assertLess(len(text), 1500)

    def test_agent_method_has_ten_stages_and_fictional_case(self):
        text = (self.space / ".space" / "agent-customization.md").read_text(encoding="utf-8")
        for n in range(0, 11):
            self.assertIn(f"| {n} |", text)
        self.assertIn("Fictional case", text)

    def test_agents_md_has_the_two_tables(self):
        text = (self.space / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Module write-owner table", text)
        self.assertIn("Required-reading table", text)
        self.assertIn("| work | `work/` |", text)

    def test_config_is_valid_and_lists_modules(self):
        cfg = json.loads((self.space / ".space" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["modules"], ["work", "personal"])
        self.assertEqual(cfg["backup"]["status"], "pending")
        self.assertIn("work/STATE.md", cfg["shared_files"])

    def test_hooks_registered_with_absolute_scripts_in_root_and_modules(self):
        for folder in ["", "work/", "personal/"]:
            data = json.loads((self.space / f"{folder}.claude" / "settings.json").read_text(encoding="utf-8"))
            blob = json.dumps(data, ensure_ascii=False)
            hooks_dir = str(self.space / ".space" / "hooks").replace("\\", "/")
            self.assertIn(hooks_dir + "/pre_write_guard.py", blob.replace("\\\\", "/"), folder)
            self.assertIn(hooks_dir + "/turn_check.py", blob.replace("\\\\", "/"), folder)
            self.assertEqual(set(data["hooks"]), {"PreToolUse", "SessionStart", "UserPromptSubmit"})

    def test_self_check_passes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_mod.main(["--check", "--target", str(self.space)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(json.loads(out.getvalue())["ok"])

    def test_self_check_fails_when_a_file_is_missing(self):
        (self.space / "PRINCIPLES.md").unlink()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_mod.main(["--check", "--target", str(self.space)])
        self.assertEqual(code, 1)

    def test_installed_tools_run_inside_the_space(self):
        self.assertEqual(run(self.space, "state_check.py").returncode, 0)
        self.assertEqual(run(self.space, "read_rules.py", "manifest").returncode, 0)

    def test_rerun_skips_existing_files_and_never_overwrites(self):
        marker = "my own words\n"
        (self.space / "PRINCIPLES.md").write_text(marker, encoding="utf-8")
        code, out = install(self.space)
        self.assertEqual(code, 0)
        self.assertEqual((self.space / "PRINCIPLES.md").read_text(encoding="utf-8"), marker)
        files = {f["file"]: f["result"] for f in json.loads(out)["files"]}
        self.assertTrue(files["PRINCIPLES.md"].startswith("skipped"))

    def test_force_replaces_but_backs_up_first(self):
        (self.space / "PRINCIPLES.md").write_text("old text\n", encoding="utf-8")
        code, _ = install(self.space, extra=["--force"])
        self.assertEqual(code, 0)
        saved = list((self.space / ".space" / "history" / "write-backups").rglob("PRINCIPLES@*.md"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(encoding="utf-8"), "old text\n")

    def test_existing_claude_settings_are_merged_not_replaced(self):
        target = Path(tempfile.mkdtemp()).resolve() / "S"
        (target / ".claude").mkdir(parents=True)
        (target / ".claude" / "settings.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
        code, _ = install(target)
        self.assertEqual(code, 0)
        data = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIn("PreToolUse", data["hooks"])
        install(target)  # second run must not duplicate the hook entries
        data2 = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data2["hooks"]["PreToolUse"]), 1)

    def test_broken_claude_settings_are_left_alone(self):
        target = Path(tempfile.mkdtemp()).resolve() / "S"
        (target / ".claude").mkdir(parents=True)
        (target / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
        code, out = install(target)
        self.assertEqual(code, 0)
        self.assertEqual((target / ".claude" / "settings.json").read_text(encoding="utf-8"), "{not json")
        self.assertIn("not valid JSON", out)


class InstallChinese(SpaceCase):
    language = "zh-CN"

    def test_chinese_files_and_passphrase(self):
        card = (self.space / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertRegex(card, r"校验暗号：\S+")
        for rel in ["AGENTS.md", "STATE.md", "BACKUP.md", ".space/agent-customization.md"]:
            self.assertNotIn("{{", (self.space / rel).read_text(encoding="utf-8"))
        self.assertIn("模块写入方表", (self.space / "AGENTS.md").read_text(encoding="utf-8"))

    def test_self_check_passes_in_chinese(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = setup_mod.main(["--check", "--target", str(self.space)])
        self.assertEqual(code, 0, out.getvalue())

    def test_chinese_module_names_work(self):
        target = Path(tempfile.mkdtemp()).resolve() / "S"
        code, _ = install(target, "zh-CN", modules="工作,个人")
        self.assertEqual(code, 0)
        self.assertTrue((target / "工作" / "STATE.md").is_file())
        self.assertIn("](工作/STATE.md)", (target / "STATE.md").read_text(encoding="utf-8"))
        self.assertEqual(run(target, "state_check.py").returncode, 0)


class InstallErrors(unittest.TestCase):
    def call(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            try:
                code = setup_mod.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, err.getvalue()

    def base(self, target):
        return ["--target", str(target), "--name", "A", "--os", "mac", "--always-on", "no", "--modules", "work"]

    def test_missing_arguments_exit_2(self):
        code, err = self.call(["--target", tempfile.mkdtemp(), "--yes"])
        self.assertEqual(code, 2)
        self.assertIn("--name", err)

    def test_no_consent_exit_2_and_nothing_written(self):
        target = Path(tempfile.mkdtemp()) / "S"
        code, err = self.call(self.base(target))
        self.assertEqual(code, 2)
        self.assertFalse(target.exists())

    def test_bad_module_names_rejected(self):
        for bad in ["../x", "a/b", ".git", ".space", "a b!"]:
            target = Path(tempfile.mkdtemp()) / "S"
            argv = self.base(target)
            argv[argv.index("--modules") + 1] = bad
            code, err = self.call(argv + ["--yes"])
            self.assertNotEqual(code, 0, bad)
            self.assertFalse((target / "STATE.md").exists(), bad)


if __name__ == "__main__":
    unittest.main()
