# pg-memo

PostgreSQL-backed memory skill for AI agents. Provides durable, structured storage with full-text and trigram search, multi-workspace scoping, and a consistent JSON output interface.

## Highlights

- **Structured storage** — save facts, preferences, decisions, lessons, and more with `--kind`, `--scope`, and `--tags`
- **Full-text + trigram search** — powered by `pg_trgm`, `unaccent`, and tsvector FTS indexes
- **Multi-workspace scopes** — namespace entries per workspace via `--scope`
- **JSON by default, `--markdown` for human-readable output** — every command supports both
- **Prune and vacuum** — age-based and cardinality-based pruning; `vacuum` reclaims space after bulk deletes
- **Pure Python runtime** — single script, no daemon, connects directly over TCP/IP

## Installation

```bash
./install.sh          # installs pg-memo command + config
./install-skill.sh    # installs SKILL.md into OpenClaw workspaces
```

`install.sh` places the launcher at `~/.local/bin/pg-memo` and the runtime at `~/.local/share/pg-memo/pg_memo.py`. It creates `~/.config/pg-memo/config.json` and optionally writes the password file. Existing config and secrets are preserved unless `--force-config` / `--force-password` are passed.

**Key options:**

| Option | Description |
|---|---|
| `-y` / `--yes` | Non-interactive |
| `--bin-dir <path>` | Override install location for the launcher |
| `--runtime-dir <path>` | Override install location for the Python script |
| `-d/u/h/p` | Database, user, host, port |
| `--password <value>` / `--password-file <path>` | Credential source |
| `--force-config` / `--force-password` | Overwrite existing config or password |

`install-skill.sh` auto-discovers OpenClaw workspaces or accepts explicit targets:

```bash
./install-skill.sh -y ~/workspace-a/skills ~/workspace-b/skills
```

## Configuration

Default config: `~/.config/pg-memo/config.json`

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

**Precedence:** CLI args → environment variables → config file → built-in defaults

**Environment variables:** `PG_MEMO_CONFIG`, `PG_MEMO_HOST`, `PG_MEMO_PORT`, `PG_MEMO_DB`, `PG_MEMO_USER`, `PG_MEMO_PASSWORD`, `PG_MEMO_PASSWORD_FILE`

## Python dependency

Requires `psycopg` or `psycopg2`. Preferred:

```bash
python3 -m pip install --user "psycopg[binary]"
# or: sudo apt install python3-psycopg
```

Fallback: `psycopg2-binary` / `python3-psycopg2`. If neither is present, the script returns a structured dependency error.

## Schema bootstrap

Apply migrations in order using any PostgreSQL client:

```bash
PGPASSWORD="$(cat ~/.config/pg-memo/password)" \
psql -h 127.0.0.1 -p 5432 -U openclaw -d openclaw -v ON_ERROR_STOP=1 \
  -f sql/001_init.sql -f sql/002_title_trgm.sql
```

`001_init.sql` creates the `memory_items` table, `pg_trgm`/`unaccent` extensions, timestamp and FTS triggers, and indexes on scope, kind, tags, FTS, and source date. `002_title_trgm.sql` adds a trigram index on the title field.

## Commands

```bash
pg-memo config                                        # show resolved config
pg-memo save --kind fact --scope main \
  --summary "..." --content "..." --tags a b          # save a memory
pg-memo update --id 42 --summary "..."                # patch any field(s)
pg-memo get --id 42                                   # fetch by id
pg-memo search --query "text" [--kind K] [--scope S] [--tags T] [--limit N]
pg-memo recent [--kind K] [--scope S] [--limit N]
pg-memo scopes                                        # list scopes in the database
pg-memo delete --ids 1 2 3
pg-memo prune --older-than 90 [--dry-run]             # age-based prune
pg-memo prune --keep-latest 4 --kind K --scope S [--dry-run]  # cardinality prune
pg-memo vacuum                                        # VACUUM ANALYZE + table stats
```

Add `--markdown` to any command for human-readable output.

**Fallback paths** (if not on `PATH`): `~/.local/bin/pg-memo` · `~/.openclaw/skills/pg-memo/scripts/pg-memo`
