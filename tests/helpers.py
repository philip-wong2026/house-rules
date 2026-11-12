"""Shared helpers for the tests: install a throw-away Space and run its tools as a user would."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import setup as setup_mod  # noqa: E402


def install(target, language="en", modules="work,personal", extra=None):
    argv = ["--target", str(target), "--name", "Alex", "--os", "linux", "--language", language,
            "--always-on", "no", "--ai", "TestAI", "--chat-channel", "none", "--modules", modules,
            "--yes"] + (extra or [])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = setup_mod.main(argv)
    return code, out.getvalue()


def run(space, script, *args, stdin=None):
    """Run an installed tool in the Space like a user would; returns CompletedProcess."""
    return subprocess.run([sys.executable, str(Path(space) / ".space" / script), *map(str, args)],
                          cwd=str(space), input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=60)


class SpaceCase(unittest.TestCase):
    language = "en"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.space = Path(self._tmp.name).resolve() / "Space"
        code, out = install(self.space, self.language)
        self.assertEqual(code, 0, out)

    def write(self, rel, text):
        path = self.space / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def config(self, **changes):
        path = self.space / ".space" / "config.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
