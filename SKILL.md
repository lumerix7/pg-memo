---
name: pg-memo
description: PostgreSQL-backed memory. Save concise notes, search stored memory, and retrieve recent items.
---

# Pg Memo

Use the host-local `pg-memo` command.

## Purpose

Use this skill to:

- save durable notes to PostgreSQL
- search prior notes
- retrieve recent memory
- keep memory structured without requiring vectors


## Usage

```bash
pg-memo <command> [options]
pg-memo --help
pg-memo <command> --help
```

## Common commands

```
pg-memo save --kind fact --scope main --summary "User prefers professional tone"
pg-memo search --query "professional tone"
pg-memo recent --limit 10
pg-memo get --id 1
pg-memo delete --ids 1 2 3
```

Default installed command location:

- `~/.local/bin/pg-memo`

If `~/.local/bin` is not on `PATH`, use the full installed path or reinstall with `install.sh --bin-dir <path-on-PATH>`.


## Rules

- Summarize first, then save.
- Store durable facts, preferences, decisions, and concise summaries.
- Do not store passwords, API keys, tokens, private keys, or raw credentials.
- Prefer short structured notes over raw transcript dumps.
