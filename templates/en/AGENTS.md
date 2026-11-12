# AGENTS.md — master rules of {{user}}'s Space

This file is the detailed rulebook. The short version that every session must obey is in [CLAUDE.md](CLAUDE.md). Look up a chapter only when you need it. When a rule changes, change it here and nowhere else.

## 1. Start of every session
1. Read the base card in `CLAUDE.md`. If you can answer "what is the passphrase?", the card was loaded.
2. Read the project's README section "Current status" (or the module `STATE.md`) to see where things stand.
3. Before writing files, look up the two tables below: who writes this folder, and what to read first.
4. When setting direction or making trade-offs, read `PRINCIPLES.md` once.

## 2. Module write-owner table
Each module (top-level folder) has exactly one default write owner. Others read, and ask the owner (or write a note in the owner's `STATE.md` "Open" line) instead of editing.

{{modules_table}}

- The default is a convention, not a lock. When {{user}} says "do it in this session", do it there.
- Shared files (root `STATE.md`, `AGENTS.md`, `CLAUDE.md`, module `STATE.md`) are written through `{{py}} .space/shared_write.py` (compare-and-swap on the SHA-256), never by overwriting a stale copy.

## 3. Required-reading table
| Kind of work | Read first |
|---|---|
| Any work | `CLAUDE.md`, this file's chapters 1–2 |
| Setting direction, trade-offs | `PRINCIPLES.md` |
| Changing a module's state | that module's `STATE.md` and `.space/state-maintenance.md` |
| Starting or retiring a project | `.space/project-three-rules.md` |
| Building an assistant for someone | `.space/agent-customization.md` |
| Backup or restore | `BACKUP.md` |

Add a row whenever a new kind of work gets its own rules. `{{py}} .space/read_rules.py manifest` lists the required files with sizes and SHA-256 so you can see nothing is missing.

## 4. State and history
- Three layers: root `STATE.md` (navigation, read every turn, at most {{root_limit}} characters) → module `STATE.md` (one current entry per matter, at most {{module_limit}} characters) → dated records and `.space/history/` (process, evidence, old text; read on demand).
- One matter = one entry. A new state replaces the old entry; old text is kept in a dated record, not piled into the entry.
- Each entry: current state (source date) / open / next step / evidence. Template in `.space/state-maintenance.md`.
- A decision or progress is written into the README "Current status" or `STATE.md` on the spot. Before finishing, check that everything decided this session is recorded.
- Nothing is called "done" unless it was verified; write what was verified, on which date, from what source. Keep facts, inferences and open questions apart.
- Check: `{{py}} .space/state_check.py` (read-only). At 80% of a limit, tidy first; never truncate.

## 5. Files: backup, recycle, conflicts
- Before changing a setting or program: `{{py}} .space/backup.py <file>` (stored under `.space/history/write-backups/`). No `.bak` next to originals.
- Clean-up never deletes: `{{py}} .space/recycle.py <path> --reason "..." --who <agent>` moves it into `.space/recycle-bin/` (kept {{keep_days}} days, restorable with `--restore`). Permanent deletion needs {{user}}'s consent.
- A sync-conflict copy is evidence: compare, keep both sides, then merge. Never overwrite one with the other.
- Read each target file again right before writing it. One file, one writing session at a time.

## 6. Hard lines
- Ask {{user}} first before: spending money, sending messages to other people, permanent deletion, changing external originals, changing network/proxy settings, logging in to accounts.
- Passwords, tokens and keys never go into ordinary files. Keep them in the password manager.
- Do only what was asked this time.
- Report in plain language: conclusion first, then evidence, limits and next step.

## 7. Safety net (what is and is not enforced)
`.claude/settings.json` registers two hooks if you use Claude Code at the Space root: a write guard (`.space/hooks/pre_write_guard.py`) that refuses obvious slips, and a turn check (`.space/hooks/turn_check.py`) that reports problems at the start of each turn. They are speed bumps against slips, not a security boundary. Other AI clients may ignore them; the rules above still apply.
