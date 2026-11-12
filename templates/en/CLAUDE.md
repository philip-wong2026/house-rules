# {{user}}'s Space — work card

Rules every session must obey. Details are in [AGENTS.md](AGENTS.md); look up a chapter when you need it.

## Base card (this section is the master copy; edit it here only)
Self-check passphrase: {{passphrase}} (in a new session, ask "what is the base-card passphrase?"; if it can be answered, this card was loaded automatically)
Updated: {{date}}. Read before editing; one session edits at a time; keep one line per fact and link to details.

#### Person
- Call them: {{user}}.
- How to talk to them: plain language, conclusion first.

#### Devices
{{devices_table}}

#### AI and chat channel
- AI in use: {{ai}}.
- Chat channel: {{channel}}.

#### How to reach the other computer / outside
- Always-on computer: {{always_on}}.
- Offsite backup: see [BACKUP.md](BACKUP.md). Status: {{backup_status}}.

#### Where to look
- Rules: [AGENTS.md](AGENTS.md). State: [STATE.md](STATE.md). Direction: [PRINCIPLES.md](PRINCIPLES.md).
- Anything about a project: that project's README "Current status".

## Start of a session (once, not every message)
1. Read the project README "Current status" or the module `STATE.md`.
2. Before writing files, look up AGENTS.md: "Module write-owner table" and "Required-reading table".
3. Before setting direction or making trade-offs, read `PRINCIPLES.md` once.

## Bottom lines (always on)
- Call the user {{user}}; give times in the user's local time and check the current time before mentioning one.
- Do only what was asked. Ask first before spending money, messaging other people, permanent deletion, changing external originals, or changing network settings.
- Keep facts, inferences and open questions apart; cite source and date for key conclusions; never say "done" for something unverified.
- No passwords, tokens or keys in ordinary files.
- Read the target file again before writing; one file, one writing session; if you find a conflict copy keep both sides, never overwrite.
- Back up with `{{py}} .space/backup.py <file>` before changing settings or programs; clean up with `{{py}} .space/recycle.py`, never delete.
- When something is decided or progresses, write it into the README "Current status" or `STATE.md` on the spot; check again before finishing.
- Report in plain language: conclusion first, then evidence, limits, next step.
