# .claude/

Project context for Claude Code lives in **[`../CLAUDE.md`](../CLAUDE.md)** at the
repository root, not in here — that is the path Claude Code loads automatically at
the start of every session, so it is the only place a note is guaranteed to be read.

This directory holds tooling config:

| File | Tracked | Purpose |
|---|---|---|
| `settings.local.json` | no | Per-machine permissions and preferences |
| `settings.json` | yes, if created | Team-wide settings — hooks, shared permissions |
| `skills/` | yes, if created | Project-specific skills |

`.gitignore` previously excluded this whole directory, which meant anything written
here for the team never left the machine that wrote it. It now excludes only
`settings.local.json` and other `*.local.json`.
