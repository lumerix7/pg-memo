#!/usr/bin/env python3
import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = "~/.config/pg-memo/config.json"


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


def cmd_config(args: argparse.Namespace) -> int:
    s = resolve_settings().copy()
    if s.get("password"):
        s["password"] = "***redacted***"
    return print_json({"status": "ok", "action": "config", "config": s})


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
    return print_json({"status": "ok", "action": "save", "item": out})


def cmd_search(args: argparse.Namespace) -> int:
    sql = """
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
      WHERE
        fts @@ plainto_tsquery('simple', %s)
        OR coalesce(title, '') %% %s
        OR coalesce(summary, '') %% %s
        OR content %% %s
        OR coalesce(title, '') ILIKE '%%' || %s || '%%'
        OR coalesce(summary, '') ILIKE '%%' || %s || '%%'
        OR content ILIKE '%%' || %s || '%%'
    ), final AS (
      SELECT *, (fts_rank * 10.0 + sim_rank) AS score
      FROM ranked
      ORDER BY score DESC, updated_at DESC
      LIMIT %s
    )
    SELECT COALESCE(json_agg(final), '[]'::json) FROM final;
    """
    q = args.query
    out = execute_json_query(sql, (q, q, q, q, q, q, q, q, q, q, q, args.limit))
    return print_json({"status": "ok", "action": "search", "query": args.query, "results": out or []})


def cmd_recent(args: argparse.Namespace) -> int:
    sql = """
    WITH rows AS (
      SELECT id, kind, scope, title, summary, left(content, 280) AS snippet, tags, created_at, updated_at
      FROM memory_items
      ORDER BY updated_at DESC, id DESC
      LIMIT %s
    )
    SELECT COALESCE(json_agg(rows), '[]'::json) FROM rows;
    """
    out = execute_json_query(sql, (args.limit,))
    return print_json({"status": "ok", "action": "recent", "results": out or []})


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
        return print_json({"status": "not_found", "action": "get", "id": args.id})
    return print_json({"status": "ok", "action": "get", "item": obj})


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
    return print_json({
        "status": status,
        "action": "delete",
        "requested_ids": ids,
        "deleted_ids": deleted_ids,
    })


def build_parser() -> argparse.ArgumentParser:
    settings = resolve_settings()
    parser = argparse.ArgumentParser(description="Pg Memo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_config = sub.add_parser("config")
    p_config.set_defaults(func=cmd_config)

    p_save = sub.add_parser("save")
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
    p_save.set_defaults(func=cmd_save)

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=settings["default_search_limit"])
    p_search.set_defaults(func=cmd_search)

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--limit", type=int, default=settings["default_recent_limit"])
    p_recent.set_defaults(func=cmd_recent)

    p_get = sub.add_parser("get")
    p_get.add_argument("--id", type=int, required=True)
    p_get.set_defaults(func=cmd_get)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--ids", type=int, nargs="+", required=True)
    p_delete.set_defaults(func=cmd_delete)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.cmd == "save":
            json.loads(args.metadata)
        return args.func(args)
    except Exception as e:
        return print_json({"status": "error", "command": args.cmd, "error": str(e)})


if __name__ == "__main__":
    raise SystemExit(main())
