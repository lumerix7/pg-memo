---
name: pg-memo
description: PostgreSQL-backed long-term memory. Save, update, search, and browse structured notes with full-text + trigram search.
---

# Pg Memo

Use the host-local `pg-memo` command.

## Purpose

`pg-memo` is the **primary long-term searchable memory store**.

- `memory/YYYY-MM-DD.md` — raw daily logs (ephemeral, file-based)
- `MEMORY.md` — curated index / summary of what's in pg-memo
- `pg-memo` — durable structured store; the source of truth for anything that needs to survive and be searched later

When in doubt about where to save something durable: **use pg-memo**.

## When to use

| Situation | Action |
|---|---|
| "remember this" | `pg-memo save` + update MEMORY.md index |
| Looking up a past fact or decision | `pg-memo search` |
| Browsing recent notes | `pg-memo recent` |
| Updating a stale memory | `pg-memo update --id N` |
| Removing obsolete entries | `pg-memo delete --ids ...` |

## Kind taxonomy

Use consistent `--kind` values so filtering works:

| kind | meaning |
|---|---|
| `fact` | stable fact about the user, system, or world |
| `preference` | user preference or style choice |
| `decision` | a decision that was made and why |
| `lesson` | something learned from experience |
| `note` | general observation or reminder |
| `task` | a deferred task or follow-up |
| `summary` | a condensed recap of a session or topic |
| `context` | background context for a project or workflow |

## Usage

```bash
pg-memo <command> [options]
pg-memo --help
pg-memo <command> --help
```

## Commands

```bash
# Save a new memory
pg-memo save --kind preference --summary "User prefers concise responses" \
  --content "User wants answers under 100 words unless complexity demands more" \
  --tags user style

# Update an existing memory
pg-memo update --id 42 --summary "Updated preference: be concise but thorough for complex tasks"

# Search memory (full-text + fuzzy)
pg-memo search --query "response style"
pg-memo search --query "postgres" --kind decision --limit 5
pg-memo search --query "tone" --scope main --tags style
pg-memo search --query "tone" --markdown

# Browse recent entries
pg-memo recent --limit 10
pg-memo recent --kind lesson
pg-memo recent --scope main --kind decision --markdown

# Get full content of a specific item
pg-memo get --id 42

# Discover scopes in the database
pg-memo scopes --markdown

# Delete entries
pg-memo delete --ids 1 2 3

# Show resolved config
pg-memo config
```

## Multi-workspace scopes

`pg-memo` is shared across workspaces. Use `--scope` to namespace entries per workspace.

**Convention:**

| Workspace | Scope |
|---|---|
| `openclaw-workspace` (default/primary) | `default` |
| `openclaw-main-workspace` | `main` |

Set the scope in each workspace's config (`~/.config/pg-memo/config.json`):

```json
"defaults": { "scope": "default" }
```

Omitting `--scope` uses the configured default. Always pass `--scope` explicitly when saving to keep entries cleanly separated.

```bash
# Discover what scopes exist
pg-memo scopes
pg-memo scopes --markdown

# Save to a specific scope
pg-memo save --kind fact --scope default --summary "..."
pg-memo save --kind preference --scope main --summary "..."

# Query within a scope
pg-memo search --query "tone" --scope default
pg-memo recent --scope main --kind decision
```

## MEMORY.md index format

Each workspace has its own `MEMORY.md`. It is a **human-readable index** into pg-memo, not the full content.

**Header (required):**

```markdown
<!-- pg-memo scope: default | last-synced: 2026-03-16 -->
```

**Body — sectioned by kind, each entry has a `[#id]` ref:**

```markdown
## Preferences
- [#12] User prefers professional tone
- [#15] Prefer Codex CLI for most coding tasks

## Decisions
- [#8] GitHub Copilot CLI preferred for git commit work only

## Identity
- [#1] Assistant identity: Nora 🌊
```

**Rules:**
- After `pg-memo save`, append `[#<new_id>] <summary>` to the relevant section in MEMORY.md
- After `pg-memo update --id N`, update the corresponding line in MEMORY.md
- After `pg-memo delete --ids N`, remove the corresponding lines from MEMORY.md
- To read the full content of any item: `pg-memo get --id N --markdown`
- Entries without an id yet (not yet in pg-memo) use `[#?]` as a placeholder



All commands output JSON by default. Add `--markdown` to any command to get human-readable output instead — useful when displaying results directly in chat:

| Command | Markdown output |
|---|---|
| `search` / `recent` | formatted table |
| `get` | detail block with all fields |
| `save` / `update` | `✅ Saved/Updated #ID · kind · summary` |
| `delete` | `🗑️ Deleted: 1, 2, 3` |
| `config` | fenced JSON block |

## Rules

- Summarize first, then save. Store the essence, not a transcript.
- Store durable facts, preferences, decisions, lessons, and concise summaries.
- Do not store passwords, API keys, tokens, private keys, or raw credentials.
- When saving, always provide `--content` for the full text and `--summary` for a short one-liner.
- Use `--tags` to make entries easier to filter later.
- After saving something important, update `MEMORY.md` as an index entry.

## Default installed command location

- `~/.local/bin/pg-memo`

If `~/.local/bin` is not on `PATH`, use the full installed path or reinstall with `install.sh --bin-dir <path-on-PATH>`.

