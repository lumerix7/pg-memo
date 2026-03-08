import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pg_memo.py"
SPEC = importlib.util.spec_from_file_location("pg_memo_under_test", MODULE_PATH)
pg_memo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pg_memo)


class PgMemoTests(unittest.TestCase):
    def test_build_parser_help_uses_pg_memo_cli_name(self) -> None:
        with patch.object(pg_memo, "resolve_settings", return_value={
            "default_scope": "main",
            "default_search_limit": 10,
            "default_recent_limit": 10,
        }):
            help_text = pg_memo.build_parser().format_help()

        self.assertIn("Usage:\n  pg-memo <command> [options]\n  pg-memo <command> -h", help_text)
        self.assertIn("Commands:", help_text)
        self.assertLess(help_text.index("Usage:"), help_text.index("Commands:"))
        self.assertFalse(help_text.startswith("usage:"))
        self.assertNotIn("pg_memo.py", help_text)

    def test_save_subcommand_help_uses_clean_prog_name(self) -> None:
        with patch.object(pg_memo, "resolve_settings", return_value={
            "default_scope": "main",
            "default_search_limit": 10,
            "default_recent_limit": 10,
        }):
            with self.assertRaises(SystemExit):
                with patch("sys.argv", ["pg_memo.py", "save", "-h"]):
                    pg_memo.build_parser().parse_args()

            help_text = pg_memo.build_parser()._subparsers._group_actions[0].choices["save"].format_help()

        self.assertIn("usage: pg-memo save [-h] --kind KIND", help_text)
        self.assertNotIn("pg-memo <command> [options] save", help_text)

    def test_load_postgres_driver_raises_clear_error_when_no_driver_installed(self) -> None:
        with patch.object(pg_memo.importlib, "import_module", side_effect=ModuleNotFoundError()):
            with self.assertRaisesRegex(RuntimeError, "missing PostgreSQL client library"):
                pg_memo.load_postgres_driver()

    def test_connect_uses_psycopg2_with_autocommit(self) -> None:
        fake_conn = SimpleNamespace(autocommit=False)
        fake_driver = SimpleNamespace(connect=Mock(return_value=fake_conn))

        with patch.object(pg_memo, "resolve_settings", return_value={
            "host": "127.0.0.1",
            "port": 5432,
            "database": "openclaw",
            "user": "openclaw",
            "password": "secret",
        }):
            with patch.object(pg_memo, "load_postgres_driver", return_value=("psycopg2", fake_driver)):
                conn, driver_name = pg_memo.connect()

        self.assertIs(conn, fake_conn)
        self.assertEqual(driver_name, "psycopg2")
        self.assertTrue(fake_conn.autocommit)

    def test_execute_json_query_decodes_string_json_from_psycopg2(self) -> None:
        fake_cursor = Mock()
        fake_cursor.fetchone.return_value = ('{"status":"ok"}',)
        fake_cursor.__enter__ = Mock(return_value=fake_cursor)
        fake_cursor.__exit__ = Mock(return_value=False)
        fake_conn = Mock()
        fake_conn.cursor.return_value = fake_cursor

        with patch.object(pg_memo, "connect", return_value=(fake_conn, "psycopg2")):
            result = pg_memo.execute_json_query("SELECT 1")

        self.assertEqual(result, {"status": "ok"})
        fake_cursor.execute.assert_called_once_with("SELECT 1", ())
        fake_conn.close.assert_called_once()

    def test_cmd_search_uses_pg_trgm_percent_operator(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> list[object]:
            captured["sql"] = sql
            captured["params"] = params
            return []

        args = SimpleNamespace(query="tone", limit=5, scope=None, kind=None, tags=None)
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0):
                pg_memo.cmd_search(args)

        self.assertIn("coalesce(title, '') %% %s", captured["sql"])
        self.assertEqual(captured["params"], ("tone",) * 11 + (5,))

    def test_cmd_search_appends_scope_kind_tags_filters(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> list[object]:
            captured["sql"] = sql
            captured["params"] = params
            return []

        args = SimpleNamespace(query="tone", limit=5, scope="main", kind="preference", tags=["style"])
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0):
                pg_memo.cmd_search(args)

        self.assertIn("scope = %s", captured["sql"])
        self.assertIn("kind = %s", captured["sql"])
        self.assertIn("tags @> %s::jsonb", captured["sql"])
        self.assertIn("main", captured["params"])
        self.assertIn("preference", captured["params"])
        self.assertIn('["style"]', captured["params"])

    def test_cmd_recent_no_filters(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> list[object]:
            captured["sql"] = sql
            captured["params"] = params
            return []

        args = SimpleNamespace(limit=5, scope=None, kind=None)
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0):
                pg_memo.cmd_recent(args)

        self.assertNotIn("WHERE", captured["sql"])
        self.assertEqual(captured["params"], (5,))

    def test_cmd_recent_with_scope_and_kind_filters(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> list[object]:
            captured["sql"] = sql
            captured["params"] = params
            return []

        args = SimpleNamespace(limit=3, scope="main", kind="decision")
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0):
                pg_memo.cmd_recent(args)

        self.assertIn("WHERE", captured["sql"])
        self.assertIn("scope = %s", captured["sql"])
        self.assertIn("kind = %s", captured["sql"])
        self.assertEqual(captured["params"], ("main", "decision", 3))

    def test_cmd_update_builds_dynamic_set_clause(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> dict[str, object]:
            captured["sql"] = sql
            captured["params"] = params
            return {"id": 7, "summary": "Updated"}

        args = SimpleNamespace(id=7, kind=None, scope=None, title=None,
                               summary="Updated", content=None, tags=None, metadata=None)
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_update(args)

        self.assertIn("UPDATE memory_items", captured["sql"])
        self.assertIn("summary = %s", captured["sql"])
        self.assertEqual(captured["params"], ("Updated", 7))
        fake_print.assert_called_once_with({
            "status": "ok",
            "action": "update",
            "item": {"id": 7, "summary": "Updated"},
        })

    def test_cmd_update_returns_error_when_no_fields_given(self) -> None:
        args = SimpleNamespace(id=7, kind=None, scope=None, title=None,
                               summary=None, content=None, tags=None, metadata=None)
        with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
            pg_memo.cmd_update(args)

        call_args = fake_print.call_args[0][0]
        self.assertEqual(call_args["status"], "error")
        self.assertEqual(call_args["action"], "update")

    def test_cmd_update_returns_not_found_when_no_row_matched(self) -> None:
        args = SimpleNamespace(id=999, kind=None, scope=None, title=None,
                               summary="x", content=None, tags=None, metadata=None)
        with patch.object(pg_memo, "execute_json_query", return_value=None):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_update(args)

        fake_print.assert_called_once_with({
            "status": "not_found",
            "action": "update",
            "id": 999,
        })

    def test_print_markdown_search_renders_table(self) -> None:
        import io, sys
        obj = {
            "status": "ok",
            "action": "search",
            "query": "tone",
            "results": [
                {"id": 1, "kind": "preference", "scope": "main", "title": "Tone",
                 "snippet": "Be concise", "tags": ["style"], "updated_at": "2026-03-16T09:00:00Z"},
            ],
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("| ID |", out)
        self.assertIn("Tone", out)
        self.assertIn("`style`", out)

    def test_print_markdown_save_renders_confirmation(self) -> None:
        import io, sys
        obj = {
            "status": "ok",
            "action": "save",
            "item": {"id": 7, "kind": "fact", "summary": "Test summary"},
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("✅", out)
        self.assertIn("#7", out)
        self.assertIn("Test summary", out)

    def test_print_markdown_delete_renders_ids(self) -> None:
        import io, sys
        obj = {"status": "ok", "action": "delete", "deleted_ids": [1, 3], "requested_ids": [1, 3]}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("🗑️", captured.getvalue())
        self.assertIn("1, 3", captured.getvalue())

    def test_cmd_delete_uses_distinct_sorted_ids(self) -> None:
        captured = {}

        def fake_execute(sql: str, params: tuple[object, ...]) -> list[int]:
            captured["sql"] = sql
            captured["params"] = params
            return [1, 3]

        args = SimpleNamespace(ids=[3, 1, 3])
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_delete(args)

        self.assertIn("DELETE FROM memory_items", captured["sql"])
        self.assertEqual(captured["params"], ([1, 3],))
        fake_print.assert_called_once_with({
            "status": "ok",
            "action": "delete",
            "requested_ids": [1, 3],
            "deleted_ids": [1, 3],
        })

    def test_cmd_delete_returns_not_found_when_nothing_deleted(self) -> None:
        args = SimpleNamespace(ids=[99])
        with patch.object(pg_memo, "execute_json_query", return_value=[]):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_delete(args)

        fake_print.assert_called_once_with({
            "status": "not_found",
            "action": "delete",
            "requested_ids": [99],
            "deleted_ids": [],
        })

    # ------------------------------------------------------------------ config
    def test_cmd_config_returns_redacted_password(self) -> None:
        with patch.object(pg_memo, "resolve_settings", return_value={
            "database": "openclaw", "user": "openclaw", "password": "secret",
            "host": "127.0.0.1", "port": 5432,
        }):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                args = SimpleNamespace(markdown=False)
                pg_memo.cmd_config(args)

        cfg = fake_print.call_args[0][0]["config"]
        self.assertEqual(cfg["password"], "***redacted***")

    def test_cmd_config_markdown_renders_fenced_block(self) -> None:
        import io, sys
        with patch.object(pg_memo, "resolve_settings", return_value={
            "database": "openclaw", "user": "openclaw", "password": "",
            "host": "127.0.0.1", "port": 5432,
        }):
            args = SimpleNamespace(markdown=True)
            captured = io.StringIO()
            sys.stdout = captured
            try:
                pg_memo.cmd_config(args)
            finally:
                sys.stdout = sys.__stdout__

        self.assertIn("```json", captured.getvalue())
        self.assertIn("openclaw", captured.getvalue())

    # -------------------------------------------------------------------- save
    def test_cmd_save_inserts_and_returns_item(self) -> None:
        fake_row = {"id": 1, "kind": "fact", "scope": "main", "summary": "hi",
                    "content": "hi", "tags": [], "created_at": "2026-03-16T00:00:00Z",
                    "updated_at": "2026-03-16T00:00:00Z"}
        args = SimpleNamespace(
            kind="fact", scope="main", title="", summary="hi", content=None,
            tags=[], source_path=None, source_ref=None, related_session=None,
            metadata="{}", markdown=False,
        )
        with patch.object(pg_memo, "execute_json_query", return_value=fake_row):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_save(args)

        out = fake_print.call_args[0][0]
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["action"], "save")
        self.assertIs(out["item"], fake_row)

    # --------------------------------------------------------------------- get
    def test_cmd_get_returns_item(self) -> None:
        fake_row = {"id": 5, "kind": "note", "content": "body"}
        args = SimpleNamespace(id=5, markdown=False)
        with patch.object(pg_memo, "execute_json_query", return_value=fake_row):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_get(args)

        out = fake_print.call_args[0][0]
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["item"], fake_row)

    def test_cmd_get_returns_not_found(self) -> None:
        args = SimpleNamespace(id=99, markdown=False)
        with patch.object(pg_memo, "execute_json_query", return_value=None):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_get(args)

        self.assertEqual(fake_print.call_args[0][0]["status"], "not_found")

    def test_print_markdown_get_renders_detail_block(self) -> None:
        import io, sys
        obj = {
            "status": "ok", "action": "get",
            "item": {"id": 5, "kind": "note", "scope": "main", "title": "MyNote",
                     "summary": "A note", "content": "Full body text.",
                     "tags": ["a"], "source_path": None, "source_ref": None,
                     "created_at": "2026-03-16T00:00:00Z", "updated_at": "2026-03-16T00:00:00Z"},
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("#5", out)
        self.assertIn("MyNote", out)
        self.assertIn("Full body text.", out)

    def test_print_markdown_get_not_found(self) -> None:
        import io, sys
        obj = {"status": "not_found", "action": "get", "id": 99}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("Not found", captured.getvalue())

    # ------------------------------------------------------------------ recent
    def test_print_markdown_recent_renders_table(self) -> None:
        import io, sys
        obj = {
            "status": "ok", "action": "recent",
            "results": [
                {"id": 2, "kind": "lesson", "scope": "main", "title": None,
                 "snippet": "Learned something", "tags": [], "updated_at": "2026-03-15T00:00:00Z"},
            ],
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("| ID |", out)
        self.assertIn("Learned something", out)

    # ------------------------------------------------------------------ update
    def test_print_markdown_update_renders_confirmation(self) -> None:
        import io, sys
        obj = {
            "status": "ok", "action": "update",
            "item": {"id": 3, "kind": "preference", "summary": "New summary"},
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("✅", out)
        self.assertIn("#3", out)
        self.assertIn("New summary", out)

    def test_print_markdown_update_not_found(self) -> None:
        import io, sys
        obj = {"status": "not_found", "action": "update", "id": 99}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("Not found", captured.getvalue())

    # ------------------------------------------------------------------- _emit
    def test_emit_calls_print_json_when_markdown_false(self) -> None:
        args = SimpleNamespace(markdown=False)
        obj = {"status": "ok", "action": "recent", "results": []}
        with patch.object(pg_memo, "print_json", return_value=0) as pj:
            with patch.object(pg_memo, "print_markdown", return_value=0) as pm:
                pg_memo._emit(args, obj)
        pj.assert_called_once_with(obj)
        pm.assert_not_called()

    def test_emit_calls_print_markdown_when_markdown_true(self) -> None:
        args = SimpleNamespace(markdown=True)
        obj = {"status": "ok", "action": "recent", "results": []}
        with patch.object(pg_memo, "print_json", return_value=0) as pj:
            with patch.object(pg_memo, "print_markdown", return_value=0) as pm:
                pg_memo._emit(args, obj)
        pm.assert_called_once_with(obj)
        pj.assert_not_called()

    # ------------------------------------------------------ edge cases
    def test_print_markdown_search_empty_results(self) -> None:
        import io, sys
        obj = {"status": "ok", "action": "search", "query": "nothing", "results": []}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("No results", captured.getvalue())

    def test_print_markdown_error_renders_message(self) -> None:
        import io, sys
        obj = {"status": "error", "action": "save", "error": "db down"}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("❌", out)
        self.assertIn("db down", out)

    # ------------------------------------------------------------------ scopes
    def test_cmd_scopes_returns_scope_counts(self) -> None:
        fake_rows = [{"scope": "default", "count": 5}, {"scope": "main", "count": 2}]
        args = SimpleNamespace(markdown=False)
        with patch.object(pg_memo, "execute_json_query", return_value=fake_rows):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_scopes(args)

        out = fake_print.call_args[0][0]
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["action"], "scopes")
        self.assertEqual(out["scopes"], fake_rows)

    def test_cmd_scopes_returns_empty_list_when_db_empty(self) -> None:
        args = SimpleNamespace(markdown=False)
        with patch.object(pg_memo, "execute_json_query", return_value=None):
            with patch.object(pg_memo, "print_json", return_value=0) as fake_print:
                pg_memo.cmd_scopes(args)

        self.assertEqual(fake_print.call_args[0][0]["scopes"], [])

    def test_print_markdown_scopes_renders_table(self) -> None:
        import io, sys
        obj = {
            "status": "ok", "action": "scopes",
            "scopes": [{"scope": "default", "count": 5}, {"scope": "main", "count": 2}],
        }
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("| Scope |", out)
        self.assertIn("default", out)
        self.assertIn("main", out)

    def test_print_markdown_scopes_empty_db(self) -> None:
        import io, sys
        obj = {"status": "ok", "action": "scopes", "scopes": []}
        captured = io.StringIO()
        sys.stdout = captured
        try:
            pg_memo.print_markdown(obj)
        finally:
            sys.stdout = sys.__stdout__
        self.assertIn("empty", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
