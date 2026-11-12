# Offsite backup

Status: {{backup_status}} (set `backup.status` in `.space/config.json` to `done` only after you have restored one file from the backup yourself).

A backup on the same disk or the same sync service is not an offsite backup. Pick at least one place that survives losing this computer:

| Option | Good for | Notes |
|---|---|---|
| External drive kept in another place | everyone | copy the Space folder now and then; label the date |
| A second cloud or sync account (not the one the Space lives in) | people with a sync drive | sync is not backup: a deletion syncs too, so keep dated copies |
| `git` repository on a private remote | people comfortable with git | never push passwords or keys; keep it private |
| Cloud server snapshot | people with a server | check the snapshot really restores |

## How to verify (do it once)
1. Make the backup.
2. Restore one file from it into a temporary folder.
3. Open it and compare with the original.
4. Only then set `backup.status` to `done` and write the method and date in `backup.method`.

Write the method here (no passwords): {{backup_method}}
