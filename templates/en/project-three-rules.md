# The three general rules for every project description

**Why**: a chat session that is "connected to the computer" does not necessarily load `CLAUDE.md` from the Space root. The one thing every session of an AI project always carries is the project's own instruction text. So three general rules go at the very top of each project's instruction text.

**How to use**: open each project in your AI client, paste the block below at the very top of the project instruction (keep the old text after it). Use the same block for every project.

```
[Three general rules, put first]
1. At the start, read CLAUDE.md in the Space root (its "base card" has devices, subscriptions, assistants and how to connect; some sessions do not load it automatically, so read it yourself), then the "Current status" of this project's README. Reading the base card's passphrase proves you read it.
2. When I ask "is it done" or "how is task X going": look it up in the task list or the project's STATE first and answer with its update time. If there is no record, say "no record", never answer from impression.
3. When I decide something, write it into this project's README "Current status" (or the module STATE) on the spot, and keep the process in a dated record. Before finishing, check once more that everything I decided this session is written down.
```

**Acceptance** (do it once after pasting): in a new session of that project, (1) ask "what is the base-card passphrase?" and expect the right answer; (2) ask about a real task and expect its state and update time; (3) ask about a non-existent task and expect "no record".

## Starting and retiring projects
- **New**: create the folder with a README that has a "## Current status" section, register the folder in AGENTS.md "Module write-owner table" (or `.space/config.json` modules), create the project in your AI client with the three rules at the top of its instruction, then do the acceptance above.
- **Retire**: change the README "Current status" to retired (date and reason), mark it retired in AGENTS.md, keep the material by default; to remove files use `{{py}} .space/recycle.py` (restorable for {{keep_days}} days). Permanent deletion needs the owner's consent.
