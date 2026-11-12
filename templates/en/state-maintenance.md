# State maintenance

The rules live in AGENTS.md chapter 4. This page gives the entry template and the checks.

## Three layers
| Layer | File | What it holds |
|---|---|---|
| Root | `STATE.md` | Navigation only; read every turn |
| Module | `<module>/STATE.md` | One current entry per matter, links to details; read only the modules you touch |
| Process and history | dated records, `.space/history/` | Evidence, old text, corrections, failures; read on demand |

## Entry template
```markdown
## Matter name

- Current state (source date): what is done and how far it was actually verified.
- Open: what is still missing; keep cancelled, paused or unapproved scope.
- Next step: what can be picked up and what triggers it. Never write an old plan as if executed.
- Evidence: [detailed master copy](relative/path), [record of this change](relative/path).
```
A new state of the same matter replaces the entry. Old text is saved in a dated record that names old conclusion -> new conclusion, source date and evidence. Other matters stay untouched; do not add a "this round" paragraph every time.

## Wrapping up a task
1. Read the target again right before writing; if it changed since you read it, merge both sides, never write back an old whole file.
2. Save the old text of the entry you replace (`{{py}} .space/backup.py <file>`), then save the new result or evidence.
3. Update the detailed master copy first, then the module `STATE.md` entry.
4. Read your change back in full: are open items carried over, is the old conclusion clearly replaced, can every link be followed.
5. Say only what you verified. Content you did not re-check: write "carried over from the existing record".

## Checks
```sh
{{py}} .space/state_check.py          # sizes, links, dated headings, conflict copies, stray .bak
{{py}} .space/read_rules.py manifest  # required files with size and SHA-256
{{py}} .space/record_check.py         # project folder changed but "Current status" did not
```
They are read-only, and they do not prove anyone understood the rules.
