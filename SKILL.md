---
name: pg-memo
description: PostgreSQL-backed memory for OpenClaw using a local Python script. Save concise notes and search stored memory without vectors.
---

# Pg Memo

Pg Memo is a local memory skill for OpenClaw.

It uses:
- an OpenClaw skill
- a small local Python script
- PostgreSQL storage over TCP/IP
- relational + full-text + fuzzy search

## Purpose

Use this skill to:
- save durable notes to PostgreSQL
- search prior notes
- retrieve recent memory
- keep memory structured without requiring vectors

## Commands

```bash
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

## Status

Working initial version.

Implemented commands:
- `save`
- `search`
- `recent`
- `get`
- `delete --ids`

Current backend design:
- local Python script
- PostgreSQL reached by host/IP + port
- full-text + trigram search
