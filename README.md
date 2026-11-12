# Space Open

**Give your AI assistant a shared workspace: plain files with clear rules, so every AI session picks up where the last one stopped.**

[中文说明](README.zh-CN.md) · License: MIT · Python 3.9+ · standard library only · macOS / Windows / Linux

Space Open is a set of handoff conventions (master rules, a base card, state files) plus ten small, config-driven tools (backup, recycle bin, state check, safe shared writes, write guard and more), installed by a short conversation with your AI. Nothing is uploaded anywhere; it all lives in a folder on your computer.

## How the author uses it
The author runs it on: a Mac mini that is always on (scheduled tasks, an AI assistant reachable from the phone), a MacBook for daily work, a phone chat app (Telegram) to talk to the assistants, and an external drive for large files. You do not need any of this to start.

## What you need
**Required (the minimum):**
- one computer (it does not have to be always on)
- one AI subscription or account that can read and write files on your computer (for example Claude Code or Claude Desktop with file access, or another AI client with the same ability)
- one off-site backup (an external drive kept elsewhere, or a second cloud account); the installer guides you, see `BACKUP.md` after install

**Advanced (add later, optional):**
- an always-on computer or a cloud server: scheduled tasks, and calling the assistant from your phone
- a sync drive: your Space follows you across computers (the tools can then also watch for sync-conflict copies)
- a phone chat channel (Telegram, iMessage and the like) to talk to the assistant on the go

Python 3.9 or newer must be on the computer (the installer and the tools are plain Python, no packages to install).

## Install (by talking to your AI)
Open your AI client and say:

> Read `<link to this repo>/INSTALL.md` and install it for me.

The AI will state the safety notice and ask for your consent, ask a few questions (what to call you, Mac or Windows, always-on computer or not, which AI, where you talk to it, which areas of life/work to manage), call `setup.py`, help you set up the off-site backup, and finally ask you to open a new session and check the passphrase. See [INSTALL.md](INSTALL.md).

Or do it yourself:
```sh
python3 setup.py --target ~/Space --name Alex --os mac --language en --always-on no \
    --ai "Claude" --chat-channel none --modules work,personal --yes
python3 setup.py --check --target ~/Space
```
(Use `python` instead of `python3` on Windows.)

## What gets installed
| Path | What it is |
|---|---|
| `AGENTS.md` | master rules: write-owner table, required-reading table, state and history maintenance |
| `CLAUDE.md` | the base card, with a self-check passphrase |
| `PRINCIPLES.md` | an empty template for your own principles |
| `STATE.md`, `<area>/STATE.md` | state files (root navigation, one current entry per matter) |
| `BACKUP.md` | the off-site backup plan and how to verify it |
| `.space/*.py` | the ten tools, reading `.space/config.json` |
| `.space/hooks/` | a write guard and a per-turn check for Claude Code (registered in `.claude/settings.json`) |
| `.space/*.md` | state maintenance, "three general rules" for project descriptions, the ten-stage Agent customization method |

## The ten tools
`backup` (copy before change) · `recycle` (recycle bin instead of delete) · `read_rules` (required files with checksums) · `redact` (keep sensitive words out of shared places) · `record_check` (project changed but status did not) · `state_check` (sizes, links, conflict copies) · `shared_write` (compare-and-swap writes) · `date_copy_check` (a key date written in one place only) · `pre_write_guard` (hook) · `turn_check` (hook)

## Safety and honesty
- Your computer and data safety is your own responsibility. The tools reduce slips; they are not a security product.
- The hooks are speed bumps, not access control. The Bash check is a heuristic.
- Windows: the code avoids macOS-only commands and is meant to run on Windows, but it is verified there only by the GitHub install test (`.github/workflows/install-test.yml`), not by the author's own hands.
- Passwords and keys do not belong in these files. The privacy scan (`scripts/privacy_scan.py`) is run before every release.

## Develop
```sh
python3 -m unittest discover -s tests -v
python3 scripts/privacy_scan.py            # generic checks; set SPACE_OPEN_DENYLIST for your own list
```
