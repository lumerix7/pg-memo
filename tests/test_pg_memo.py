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

        args = SimpleNamespace(query="tone", limit=5)
        with patch.object(pg_memo, "execute_json_query", side_effect=fake_execute):
            with patch.object(pg_memo, "print_json", return_value=0):
                pg_memo.cmd_search(args)

        self.assertIn("coalesce(title, '') %% %s", captured["sql"])
        self.assertEqual(captured["params"], ("tone",) * 11 + (5,))

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


if __name__ == "__main__":
    unittest.main()
