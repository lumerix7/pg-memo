# pg-memo

PostgreSQL-backed memory skill for OpenClaw, using a small local Python script.

## Current status

Working skill package using direct PostgreSQL TCP/IP access.

## Connection model

`pg-memo` now connects directly to PostgreSQL using:

- host / IP
- port
- database
- user
- password from a local password file or environment variable

The runtime no longer uses mode switching or Docker container direct access.

## Expected local config

Default local config path:

- `~/.config/pg-memo/config.json`
- `~/.config/pg-memo/password`

Example config:

```json
{
  "postgres": {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "openclaw",
    "user": "openclaw",
    "passwordFile": "~/.config/pg-memo/password"
  },
  "defaults": {
    "scope": "main",
    "recentLimit": 10,
    "searchLimit": 10
  }
}
```

## Precedence

Settings are resolved in this order:

1. CLI arguments where applicable
2. environment variables
3. config file
4. built-in defaults

Supported environment variables:

- `PG_MEMO_CONFIG`
- `PG_MEMO_DB`
- `PG_MEMO_USER`
- `PG_MEMO_PASSWORD`
- `PG_MEMO_PASSWORD_FILE`
- `PG_MEMO_HOST`
- `PG_MEMO_PORT`

## Python dependency

The runtime requires a PostgreSQL client library for Python.

On Ubuntu/Debian systems using apt, install:

```bash
sudo apt install python3-psycopg
```

Recommended with pip:

```bash
python3 -m pip install --user "psycopg[binary]"
```

Fallbacks also work:

```bash
sudo apt install python3-psycopg2
```

or

```bash
python3 -m pip install --user psycopg2-binary
```

If neither is installed, the script returns a structured error explaining what is missing.

## Commands

Preferred installed command:

```bash
pg-memo config
pg-memo save --kind fact --scope main --summary "User prefers professional tone"
pg-memo search --query "professional tone"
pg-memo recent --limit 10
pg-memo get --id 1
pg-memo delete --ids 1 2 3
```

Fallbacks:

- `~/.local/bin/pg-memo`
- `~/.openclaw/skills/pg-memo/scripts/pg-memo`

## Install helpers

Install the local command and config helper:

```bash
./install.sh
```

Useful options:

```bash
./install.sh -y --password-file ~/.secrets/pg-memo-password
./install.sh --bin-dir ~/.local/bin
./install.sh --runtime-dir ~/.local/share/pg-memo
./install.sh --force-config -d openclaw -u openclaw -h 127.0.0.1 -p 5432
./install.sh --password 'secret' --force-password
```

Supported options:

- `-y`, `--yes`
- `--bin-dir <path>`
- `--runtime-dir <path>`
- `--password <value>`
- `--password-file <path>`
- `-d`, `--database <name>`
- `-u`, `--user <name>`
- `-h`, `--host <host>`
- `-p`, `--port <port>`
- `--force-config`
- `--force-password`

`install.sh` will:

- install the `pg-memo` launcher under `~/.local/bin/` by default
- install `pg_memo.py` under `~/.local/share/pg-memo/` by default
- create `~/.config/pg-memo/`
- create `~/.config/pg-memo/config.json`
- create or update `~/.config/pg-memo/password` when instructed
- preserve existing config unless you explicitly overwrite it
- preserve secret values unless you explicitly overwrite them

It does not print secret values.

Install the OpenClaw skill files separately:

```bash
./install-skill.sh
```

By default `install-skill.sh` resolves OpenClaw workspaces and installs into each `<workspace>/skills/pg-memo`. You can also pass explicit targets:

```bash
./install-skill.sh ~/.openclaw/skills
./install-skill.sh -y ~/workspace-a/skills ~/workspace-b/skills
```

Expected installed skill location:

- `~/.openclaw/skills/pg-memo/SKILL.md`
- `~/.openclaw/skills/pg-memo/scripts/pg-memo`
- `~/.local/bin/pg-memo`

You can override the command location for `install.sh` with `--bin-dir /path/to/bin`.

## Schema bootstrap

Initial schema file:

- `sql/001_init.sql`

Apply it using any PostgreSQL client that can reach the configured host/IP and port.

Example with `psql`:

```bash
PGPASSWORD="$(cat ~/.config/pg-memo/password)" \
psql -h 127.0.0.1 -p 5432 -U openclaw -d openclaw -v ON_ERROR_STOP=1 -f sql/001_init.sql
```

This creates:

- extensions: `pg_trgm`, `unaccent`
- table: `memory_items`
- functions: `memory_items_set_timestamps`, `memory_items_fts_update`
- triggers for timestamps and FTS updates
- indexes for scope, kind, source date, tags, FTS, and trigram search

## Tested behavior

The script is intended to support:

### Working paths

- `config` reads `~/.config/pg-memo/config.json`
- `config` reads the password from `~/.config/pg-memo/password`
- `save` inserts a row into PostgreSQL
- `recent` returns stored rows
- `search` returns matching rows
- `get` returns a row by id
- `delete --ids` removes rows by id list

### Failure and edge paths

- invalid `--metadata` JSON returns a structured error
- a search miss returns an empty `results` array
- a missing password file returns `database password not configured`
- missing Python PostgreSQL client returns a structured dependency error

### Not fully covered yet

- database unavailable over TCP/IP
- schema drift or missing table/function
- very large payloads
- concurrent writes
- update flows

### TBD delete options

- `delete --id <id>`
- `delete --query <text>`
- `delete --scope <scope>`
- `delete --all` with explicit confirmation or guardrails

## Using pg-memo from OpenClaw Web UI or Feishu

`pg-memo` is a local skill script. In OpenClaw Web UI or a Feishu chat, ask the agent in normal language to run the installed skill script.

### Examples

Save a short memory:

```text
Use pg-memo to save a daily note: Hi
```

Equivalent script call:

```bash
pg-memo save --kind daily_note --summary "Hi"
```

Search memory:

```text
Use pg-memo to search for: professional tone
```

Equivalent script call:

```bash
pg-memo search --query "professional tone"
```

Show recent memory:

```text
Use pg-memo to show recent memory
```

Equivalent script call:

```bash
pg-memo recent --limit 5
```

Show config:

```text
Use pg-memo to show config
```

Equivalent script call:

```bash
pg-memo config
```

Delete entries by id:

```text
Use pg-memo to delete memory ids 1, 2, and 3
```

Equivalent script call:

```bash
pg-memo delete --ids 1 2 3
```

## Recommended prompting style

In OpenClaw Web UI or Feishu, use plain language such as:

- `Use pg-memo to save this as a fact: User prefers professional tone.`
- `Use pg-memo to save this as a decision: Keep built-in memory search disabled for now.`
- `Use pg-memo to search for prior notes about PostgreSQL memory.`
- `Use pg-memo to show recent saved memory.`

## Current limitation

`pg-memo` is installed and usable, but it is still invoked through its script backend. It is not a built-in slash-command feature of OpenClaw.
