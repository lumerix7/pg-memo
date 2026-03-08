#!/usr/bin/env python3
import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = "~/.config/pg-memo/config.json"


class PgMemoArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        if self.prog != "pg-memo":
            return super().format_help()

        formatter = self._get_formatter()
        formatter.add_text(self.description)
        formatter.add_text("Usage:\n  pg-memo <command> [options]\n  pg-memo <command> -h")

        command_groups = []
        other_groups = []
        for group in self._action_groups:
            if not group._group_actions:
                continue
            if group.title == "Commands":
                command_groups.append(group)
            else:
                other_groups.append(group)

        for group in command_groups + other_groups:
            formatter.start_section(group.title)
            formatter.add_text(group.description)
            formatter.add_arguments(group._group_actions)
            formatter.end_section()

        formatter.add_text(self.epilog)
        return formatter.format_help()


def expand(path: str | None) -> str | None:
    if not path:
        return path
    return str(Path(path).expanduser())


def load_config() -> dict[str, Any]:
    path = expand(os.environ.get("PG_MEMO_CONFIG", DEFAULT_CONFIG_PATH))
    data: dict[str, Any] = {}
    if path and Path(path).exists():
        data = json.loads(Path(path).read_text())
    return data


def resolve_settings() -> dict[str, Any]:
    cfg = load_config()
    postgres = cfg.get("postgres", {}) if isinstance(cfg, dict) else {}
    defaults = cfg.get("defaults", {}) if isinstance(cfg, dict) else {}

    password_file = os.environ.get("PG_MEMO_PASSWORD_FILE") or postgres.get("passwordFile")
    password = os.environ.get("PG_MEMO_PASSWORD")
    if not password and password_file:
        pf = Path(expand(password_file))
        if pf.exists():
            password = pf.read_text().strip()

    return {
        "database": os.environ.get("PG_MEMO_DB") or postgres.get("database", "openclaw"),
        "user": os.environ.get("PG_MEMO_USER") or postgres.get("user", "openclaw"),
        "password": password or "",
        "host": os.environ.get("PG_MEMO_HOST") or postgres.get("host", "127.0.0.1"),
        "port": int(os.environ.get("PG_MEMO_PORT") or postgres.get("port", 5432)),
        "default_scope": defaults.get("scope", "main"),
        "default_recent_limit": int(defaults.get("recentLimit", 10)),
        "default_search_limit": int(defaults.get("searchLimit", 10)),
        "config_path": expand(os.environ.get("PG_MEMO_CONFIG", DEFAULT_CONFIG_PATH)),
        "password_file": expand(password_file),
    }


def load_postgres_driver() -> tuple[str, Any]:
    try:
        return "psycopg", importlib.import_module("psycopg")
    except ModuleNotFoundError:
        try:
            return "psycopg2", importlib.import_module("psycopg2")
        except ModuleNotFoundError:
            raise RuntimeError(
                "missing PostgreSQL client library: install 'psycopg[binary]' or 'psycopg2-binary'"
            )


def connect() -> tuple[Any, str]:
    s = resolve_settings()
    if not s["password"]:
        raise RuntimeError("database password not configured")

    driver_name, driver = load_postgres_driver()
    if driver_name == "psycopg":
        conn = driver.connect(
            host=s["host"],
            port=s["port"],
            dbname=s["database"],
            user=s["user"],
            password=s["password"],
            autocommit=True,
        )
        return conn, driver_name

    conn = driver.connect(
        host=s["host"],
        port=s["port"],
        dbname=s["database"],
        user=s["user"],
        password=s["password"],
    )
    conn.autocommit = True
    return conn, driver_name


def execute_json_query(sql: str, params: tuple[Any, ...] = ()) -> Any:
    conn, driver_name = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return None
            value = row[0]
            if driver_name == "psycopg2" and isinstance(value, str):
                return json.loads(value)
            return value
    finally:
        conn.close()


def print_json(obj: Any) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 0


def _md_tags(tags: Any) -> str:
    if not tags:
        return ""
    items = tags if isinstance(tags, list) else json.loads(tags)
    return " ".join(f"`{t}`" for t in items)


def _md_date(ts: str | None) -> str:
    if not ts:
        return ""
    return ts[:10]


def _md_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No results._"
    lines = ["| ID | Kind | Scope | Title / Snippet | Tags | Updated |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        title = r.get("title") or ""
        snippet = (r.get("snippet") or r.get("content") or "")[:80].replace("\n", " ")
        display = title if title else snippet
        display = display.replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r.get('kind', '')} | {r.get('scope', '')} "
            f"| {display} | {_md_tags(r.get('tags'))} | {_md_date(r.get('updated_at'))} |"
        )
    return "\n".join(lines)


def _md_item_detail(item: dict[str, Any]) -> str:
    lines = [f"## #{item['id']} · {item.get('kind', '')} · {item.get('scope', '')}"]
    if item.get("title"):
        lines.append(f"**Title:** {item['title']}")
    if item.get("summary"):
        lines.append(f"**Summary:** {item['summary']}")
    if item.get("tags"):
        lines.append(f"**Tags:** {_md_tags(item['tags'])}")
    if item.get("source_path"):
        lines.append(f"**Source:** {item['source_path']}" + (f" @ {item['source_ref']}" if item.get("source_ref") else ""))
    if item.get("content"):
        lines.append(f"\n**Content:**\n{item['content']}")
    lines.append(f"\n_Created: {_md_date(item.get('created_at'))}  Updated: {_md_date(item.get('updated_at'))}_")
    return "\n".join(lines)


def print_markdown(obj: Any) -> int:
    action = obj.get("action", "")
    status = obj.get("status", "ok")

    if status == "error":
        print(f"❌ **Error ({action}):** {obj.get('error', 'unknown error')}")
        return 0

    if action in ("search", "recent"):
        results = obj.get("results") or []
        if action == "search":
            print(f"**Search:** `{obj.get('query', '')}` — {len(results)} result(s)\n")
        print(_md_table(results))

    elif action == "get":
        item = obj.get("item")
        if not item or status == "not_found":
            print(f"_Not found: id {obj.get('id')}_")
        else:
            print(_md_item_detail(item))

    elif action == "save":
        item = obj.get("item") or {}
        summary = item.get("summary") or item.get("title") or ""
        print(f"✅ Saved **#{item.get('id')}** · {item.get('kind', '')} · {summary}")

    elif action == "update":
        item = obj.get("item") or {}
        if status == "not_found":
            print(f"_Not found: id {obj.get('id')}_")
        else:
            summary = item.get("summary") or item.get("title") or ""
            print(f"✅ Updated **#{item.get('id')}** · {item.get('kind', '')} · {summary}")

    elif action == "delete":
        deleted = obj.get("deleted_ids") or []
        if not deleted:
            print(f"_Not found: {obj.get('requested_ids')}_")
        else:
            print(f"🗑️ Deleted: {', '.join(str(i) for i in deleted)}")

    elif action == "config":
        cfg = obj.get("config") or {}
        print("```json\n" + json.dumps(cfg, ensure_ascii=False, indent=2) + "\n```")

    elif action == "scopes":
        rows = obj.get("scopes") or []
        if not rows:
            print("_No scopes found — database is empty._")
        else:
            lines = ["| Scope | Count |", "|---|---|"]
            for r in rows:
                lines.append(f"| {r['scope']} | {r['count']} |")
            print("\n".join(lines))

    else:
        print_json(obj)

    return 0


def _emit(args: argparse.Namespace, obj: Any) -> int:
    if getattr(args, "markdown", False):
        return print_markdown(obj)
    return print_json(obj)


def cmd_config(args: argparse.Namespace) -> int:
    s = resolve_settings().copy()
    if s.get("password"):
        s["password"] = "***redacted***"
    return _emit(args, {"status": "ok", "action": "config", "config": s})


def cmd_save(args: argparse.Namespace) -> int:
    tags_json = json.dumps(args.tags, ensure_ascii=False)
    metadata_json = args.metadata or "{}"
    sql = """
    WITH ins AS (
      INSERT INTO memory_items (
        kind, scope, title, content, summary, tags, source_path, source_ref, related_session, metadata
      ) VALUES (
        %s,
        %s,
        NULLIF(%s, ''),
        %s,
        %s,
        %s::jsonb,
        NULLIF(%s, ''),
        NULLIF(%s, ''),
        NULLIF(%s, ''),
        %s::jsonb
      )
      RETURNING id, kind, scope, title, content, summary, tags, source_path, source_ref, related_session, metadata, created_at, updated_at
    )
    SELECT row_to_json(ins) FROM ins;
    """
    out = execute_json_query(sql, (
        args.kind,
        args.scope,
        args.title or "",
        args.content or args.summary,
        args.summary,
        tags_json,
        args.source_path or "",
        args.source_ref or "",
        args.related_session or "",
        metadata_json,
    ))
    return _emit(args, {"status": "ok", "action": "save", "item": out})


def cmd_search(args: argparse.Namespace) -> int:
    filters = ["(fts @@ plainto_tsquery('simple', %s)"
               " OR coalesce(title, '') %% %s"
               " OR coalesce(summary, '') %% %s"
               " OR content %% %s"
               " OR coalesce(title, '') ILIKE '%%' || %s || '%%'"
               " OR coalesce(summary, '') ILIKE '%%' || %s || '%%'"
               " OR content ILIKE '%%' || %s || '%%')"]
    q = args.query
    params: list[Any] = [q, q, q, q, q, q, q]

    if args.scope:
        filters.append("scope = %s")
        params.append(args.scope)
    if args.kind:
        filters.append("kind = %s")
        params.append(args.kind)
    if args.tags:
        filters.append("tags @> %s::jsonb")
        params.append(json.dumps(args.tags, ensure_ascii=False))

    where = " AND ".join(filters)
    sql = f"""
    WITH ranked AS (
      SELECT
        id,
        kind,
        scope,
        title,
        summary,
        left(content, 280) AS snippet,
        tags,
        source_path,
        source_ref,
        created_at,
        updated_at,
        ts_rank(fts, plainto_tsquery('simple', %s)) AS fts_rank,
        GREATEST(
          similarity(coalesce(title, ''), %s),
          similarity(coalesce(summary, ''), %s),
          similarity(content, %s)
        ) AS sim_rank
      FROM memory_items
      WHERE {where}
    ), final AS (
      SELECT *, (fts_rank * 10.0 + sim_rank) AS score
      FROM ranked
      ORDER BY score DESC, updated_at DESC
      LIMIT %s
    )
    SELECT COALESCE(json_agg(final), '[]'::json) FROM final;
    """
    rank_params: list[Any] = [q, q, q, q]
    out = execute_json_query(sql, tuple(rank_params + params + [args.limit]))
    return _emit(args, {"status": "ok", "action": "search", "query": args.query, "results": out or []})


def cmd_recent(args: argparse.Namespace) -> int:
    filters: list[str] = []
    params: list[Any] = []

    if args.scope:
        filters.append("scope = %s")
        params.append(args.scope)
    if args.kind:
        filters.append("kind = %s")
        params.append(args.kind)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
    WITH rows AS (
      SELECT id, kind, scope, title, summary, left(content, 280) AS snippet, tags, created_at, updated_at
      FROM memory_items
      {where}
      ORDER BY updated_at DESC, id DESC
      LIMIT %s
    )
    SELECT COALESCE(json_agg(rows), '[]'::json) FROM rows;
    """
    params.append(args.limit)
    out = execute_json_query(sql, tuple(params))
    return _emit(args, {"status": "ok", "action": "recent", "results": out or []})


def cmd_get(args: argparse.Namespace) -> int:
    sql = """
    SELECT COALESCE(row_to_json(t), '{}'::json)
    FROM (
      SELECT id, kind, scope, title, content, summary, tags, source_path, source_ref, source_date, related_session, metadata, created_at, updated_at
      FROM memory_items
      WHERE id = %s::bigint
    ) t;
    """
    obj = execute_json_query(sql, (args.id,))
    if not obj:
        return _emit(args, {"status": "not_found", "action": "get", "id": args.id})
    return _emit(args, {"status": "ok", "action": "get", "item": obj})


def cmd_delete(args: argparse.Namespace) -> int:
    ids = sorted(set(args.ids))
    sql = """
    WITH deleted AS (
      DELETE FROM memory_items
      WHERE id = ANY(%s::bigint[])
      RETURNING id
    )
    SELECT COALESCE(json_agg(deleted.id ORDER BY deleted.id), '[]'::json) FROM deleted;
    """
    deleted_ids = execute_json_query(sql, (ids,))
    deleted_ids = deleted_ids or []
    status = "ok" if deleted_ids else "not_found"
    return _emit(args, {
        "status": status,
        "action": "delete",
        "requested_ids": ids,
        "deleted_ids": deleted_ids,
    })


def cmd_update(args: argparse.Namespace) -> int:
    fields: list[str] = []
    params: list[Any] = []

    if args.title is not None:
        fields.append("title = NULLIF(%s, '')")
        params.append(args.title)
    if args.summary is not None:
        fields.append("summary = %s")
        params.append(args.summary)
    if args.content is not None:
        fields.append("content = %s")
        params.append(args.content)
    if args.tags is not None:
        fields.append("tags = %s::jsonb")
        params.append(json.dumps(args.tags, ensure_ascii=False))
    if args.metadata is not None:
        fields.append("metadata = %s::jsonb")
        params.append(args.metadata)
    if args.kind is not None:
        fields.append("kind = %s")
        params.append(args.kind)
    if args.scope is not None:
        fields.append("scope = %s")
        params.append(args.scope)

    if not fields:
        return _emit(args, {"status": "error", "action": "update", "error": "nothing to update; provide at least one field to change"})

    params.append(args.id)
    set_clause = ", ".join(fields)
    sql = f"""
    WITH upd AS (
      UPDATE memory_items
      SET {set_clause}
      WHERE id = %s::bigint
      RETURNING id, kind, scope, title, content, summary, tags, source_path, source_ref, related_session, metadata, created_at, updated_at
    )
    SELECT row_to_json(upd) FROM upd;
    """
    obj = execute_json_query(sql, tuple(params))
    if not obj:
        return _emit(args, {"status": "not_found", "action": "update", "id": args.id})
    return _emit(args, {"status": "ok", "action": "update", "item": obj})


def cmd_scopes(args: argparse.Namespace) -> int:
    sql = """
    WITH rows AS (
      SELECT scope, count(*)::int AS count
      FROM memory_items
      GROUP BY scope
      ORDER BY count DESC, scope
    )
    SELECT COALESCE(json_agg(rows), '[]'::json) FROM rows;
    """
    out = execute_json_query(sql, ())
    return _emit(args, {"status": "ok", "action": "scopes", "scopes": out or []})


def build_parser() -> argparse.ArgumentParser:
    settings = resolve_settings()
    parser = PgMemoArgumentParser(
        prog="pg-memo",
        description="pg-memo\n\nLight CLI for PostgreSQL-backed memory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True, title="Commands")

    def _add_md(p: argparse.ArgumentParser) -> None:
        p.add_argument("--markdown", action="store_true", default=False,
                       help="render output as markdown instead of JSON")

    p_config = sub.add_parser("config", prog="pg-memo config")
    _add_md(p_config)
    p_config.set_defaults(func=cmd_config)

    p_save = sub.add_parser("save", prog="pg-memo save")
    p_save.add_argument("--kind", required=True)
    p_save.add_argument("--scope", default=settings["default_scope"])
    p_save.add_argument("--title")
    p_save.add_argument("--summary", required=True)
    p_save.add_argument("--content")
    p_save.add_argument("--tags", nargs="*", default=[])
    p_save.add_argument("--source-path")
    p_save.add_argument("--source-ref")
    p_save.add_argument("--related-session")
    p_save.add_argument("--metadata", default="{}", help="JSON object string")
    _add_md(p_save)
    p_save.set_defaults(func=cmd_save)

    p_search = sub.add_parser("search", prog="pg-memo search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--scope")
    p_search.add_argument("--kind")
    p_search.add_argument("--tags", nargs="*")
    p_search.add_argument("--limit", type=int, default=settings["default_search_limit"])
    _add_md(p_search)
    p_search.set_defaults(func=cmd_search)

    p_recent = sub.add_parser("recent", prog="pg-memo recent")
    p_recent.add_argument("--scope")
    p_recent.add_argument("--kind")
    p_recent.add_argument("--limit", type=int, default=settings["default_recent_limit"])
    _add_md(p_recent)
    p_recent.set_defaults(func=cmd_recent)

    p_get = sub.add_parser("get", prog="pg-memo get")
    p_get.add_argument("--id", type=int, required=True)
    _add_md(p_get)
    p_get.set_defaults(func=cmd_get)

    p_delete = sub.add_parser("delete", prog="pg-memo delete")
    p_delete.add_argument("--ids", type=int, nargs="+", required=True)
    _add_md(p_delete)
    p_delete.set_defaults(func=cmd_delete)

    p_update = sub.add_parser("update", prog="pg-memo update")
    p_update.add_argument("--id", type=int, required=True)
    p_update.add_argument("--kind")
    p_update.add_argument("--scope")
    p_update.add_argument("--title")
    p_update.add_argument("--summary")
    p_update.add_argument("--content")
    p_update.add_argument("--tags", nargs="*")
    p_update.add_argument("--metadata", help="JSON object string")
    _add_md(p_update)
    p_update.set_defaults(func=cmd_update)

    p_scopes = sub.add_parser("scopes", prog="pg-memo scopes")
    _add_md(p_scopes)
    p_scopes.set_defaults(func=cmd_scopes)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.cmd in ("save", "update") and args.metadata:
            json.loads(args.metadata)
        return args.func(args)
    except Exception as e:
        return print_json({"status": "error", "command": args.cmd, "error": str(e)})


if __name__ == "__main__":
    raise SystemExit(main())
