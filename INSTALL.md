# INSTALL.md — instructions for the AI

You are an AI assistant. The user asked you to install HouseRules on their computer. Follow these steps in order. Talk to the user in plain language, one question at a time, and do not skip the consent step. (Chinese version: [INSTALL.zh-CN.md](INSTALL.zh-CN.md); use it if the user speaks Chinese.)

## Step 0 - Get the files
Download or clone this repository to a temporary folder you can read (for example the user's Downloads folder). You need `setup.py`, `tools/` and `templates/` side by side. Check that Python 3.9+ is available (`python3 --version`, on Windows `python --version`). If it is missing, tell the user how to install it and stop; do not install software that needs administrator rights yourself.

## Step 1 - Safety notice and consent
Say this to the user in your own words and wait for a clear "yes":

> HouseRules creates folders and text files on your computer and may add hook settings for Claude Code. It does not upload anything. **Your computer and your data are your own responsibility**: keep your own backups, and do not put passwords or keys into these files. The tools reduce slips, they are not a security product. Do you agree to continue?

If the user does not clearly agree, stop. Pass `--yes` to `setup.py` only after they agree.

## Step 2 - Ask these questions (one at a time)
1. What should I call you? (`--name`)
2. Mac or Windows? (`--os mac|windows|linux`)
3. Do you have a computer that stays on all the time, or a cloud server? yes/no (`--always-on yes|no`). "No" is fine; it only matters for scheduled tasks later.
4. Which AI do you use with it? (`--ai`)
5. Where do you want to talk to your assistant: only here, or also a phone chat app (Telegram, iMessage, ...)? (`--chat-channel`)
6. Which areas should I manage? Suggest `work,personal`; folder names may be words in their language (letters, digits, `-`, `_`; no slashes). (`--modules`, comma separated)
7. Do you keep this folder on a sync drive (iCloud, Dropbox, Nutstore, ...)? (`--sync-drive yes|no`)
8. Which language for the files: English or Chinese? (`--language en|zh-CN`)
Optional: ask for their devices as `"Name|use"` (`--device`, repeatable) and any folder they want the write guard to protect (`--protect`, relative folder name).

Also decide where the Space goes: ask the user, or propose a folder such as `Space` in their home directory (`--target`). Never choose a folder that already holds important files without telling them.

## Step 3 - Install
Run (use `python` instead of `python3` on Windows; quote paths that contain spaces):

```sh
python3 setup.py --target "<folder>" --name "<name>" --os <mac|windows|linux> --language <en|zh-CN> \
    --always-on <yes|no> --ai "<ai>" --chat-channel "<channel>" --modules "<a,b>" \
    --sync-drive <yes|no> --yes
```

The command prints JSON: the list of created files, and the **passphrase** of the base card. Existing files are never overwritten silently: they are listed as "skipped". Do not use `--force` unless the user asks; it backs up the old file first.

If it fails, read the error, fix the argument, and run again. Do not edit the installed tools by hand to make an error go away.

## Step 4 - Self-check
Run `python3 setup.py --check --target "<folder>"`. Every line must be `ok: true`. Report any failure to the user in plain language.

## Step 5 - Off-site backup
Open `BACKUP.md` in the new Space and walk the user through it: choose at least one place that survives losing this computer (an external drive kept elsewhere, a second cloud account, a private git remote, a server snapshot). Have them make one backup, restore one file from it, and compare. Only then change `backup.status` in `.space/config.json` to `done` and write the method (no passwords) into `backup.method`. If they do not want to do it now, leave the status `pending`; the state check will keep reminding them.

## Step 6 - Make the AI client read the Space
- Claude Code: tell the user to open Claude Code **at the Space root folder** so `CLAUDE.md` loads automatically and the hooks in `.claude/settings.json` take effect. (Hooks on Windows are unverified until the project's install test has run; say so if you are on Windows.)
- Other clients: tell them to put the three general rules from `.space/project-three-rules.md` at the top of the project instructions, so that the base card is read.

## Step 7 - Passphrase check in a new session
Tell the user: open a **new** session in the Space and ask "what is the base-card passphrase?". It should answer with the passphrase from Step 3. If it cannot, `CLAUDE.md` is not being loaded: fix Step 6 first. Then show them `PRINCIPLES.md` (empty on purpose) and invite them to write their own principles when they are ready.

## Do not
- Do not send, upload or publish anything.
- Do not store passwords, tokens or keys in any installed file.
- Do not install software that needs administrator rights, or change network/proxy settings.
