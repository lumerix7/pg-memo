import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
INSTALL_SKILL_SCRIPT = REPO_ROOT / "install-skill.sh"


class InstallScriptTests(unittest.TestCase):
    def run_install(self, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        return subprocess.run(
            ["bash", str(INSTALL_SCRIPT), *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_install_preserves_existing_config_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config_dir = home / ".config" / "pg-memo"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            original = {
                "postgres": {
                    "host": "db.internal",
                    "port": 6432,
                    "database": "customdb",
                    "user": "customuser",
                    "passwordFile": "~/.config/pg-memo/password",
                },
                "defaults": {"scope": "team", "recentLimit": 5, "searchLimit": 7},
            }
            config_file.write_text(json.dumps(original))

            proc = self.run_install(home, "-y", "-h", "127.0.0.1", "-p", "5432")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Config file already exists; keeping current value", proc.stdout)
            self.assertEqual(json.loads(config_file.read_text()), original)

    def test_install_copies_launcher_to_custom_bin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "custom-bin"

            proc = self.run_install(home, "-y", "--bin-dir", str(bin_dir))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            launcher = bin_dir / "pg-memo"
            python_file = home / ".local" / "share" / "pg-memo" / "pg_memo.py"
            self.assertTrue(launcher.exists())
            self.assertTrue(python_file.exists())
            self.assertIn(
                'SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"',
                launcher.read_text(),
            )
            self.assertIn(
                'exec python3 "$SCRIPT_DIR/../share/pg-memo/pg_memo.py" "$@"',
                launcher.read_text(),
            )
            self.assertIn(f"Installed: {python_file}", proc.stdout)
            self.assertIn(f"Installed: {launcher}", proc.stdout)

    def test_install_force_config_overwrites_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config_dir = home / ".config" / "pg-memo"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            config_file.write_text('{"postgres":{"host":"old"}}')

            proc = self.run_install(home, "-y", "--force-config", "-h", "10.0.0.10", "-p", "6543")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = json.loads(config_file.read_text())
            self.assertEqual(written["postgres"]["host"], "10.0.0.10")
            self.assertEqual(written["postgres"]["port"], 6543)

    def test_install_does_not_overwrite_password_without_force_even_with_yes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config_dir = home / ".config" / "pg-memo"
            config_dir.mkdir(parents=True)
            password_file = config_dir / "password"
            password_file.write_text("keep-me")

            proc = self.run_install(home, "-y", "--password", "replace-me")

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Password file already exists; keeping current value", proc.stdout)
            self.assertEqual(password_file.read_text(), "keep-me")


class InstallSkillScriptTests(unittest.TestCase):
    def run_install_skill(self, home: Path, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        if path is not None:
            env["PATH"] = f"{path}:{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", str(INSTALL_SKILL_SCRIPT), *args],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_install_skill_copies_files_to_custom_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = home / "custom-skills"

            proc = self.run_install_skill(home, "-y", str(target))

            skill_dir = target / "pg-memo"
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((skill_dir / "SKILL.md").exists())
            self.assertTrue((skill_dir / "scripts" / "pg-memo").exists())
            self.assertTrue((skill_dir / "scripts" / "pg_memo.py").exists())
            self.assertTrue((skill_dir / "sql" / "001_init.sql").exists())
            self.assertTrue((skill_dir / "install-skill.sh").exists())
            self.assertIn("Installed skill to ~/custom-skills/pg-memo", proc.stdout)

    def test_install_skill_uses_openclaw_workspace_targets_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            bin_dir = home / "bin"
            workspace = home / "workspace-a"
            skills_dir = workspace / "skills"
            bin_dir.mkdir(parents=True)
            workspace.mkdir()

            openclaw = bin_dir / "openclaw"
            openclaw.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "[\n"
                f'  {{"workspace": "{workspace}"}}\n'
                "]\n"
                "EOF\n"
            )
            openclaw.chmod(0o755)

            jq = bin_dir / "jq"
            jq.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "data = json.load(sys.stdin)\n"
                "for item in data:\n"
                "    print(item['workspace'] + '/skills')\n"
            )
            jq.chmod(0o755)

            proc = self.run_install_skill(home, "-y", path=str(bin_dir))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((skills_dir / "pg-memo" / "SKILL.md").exists())
            self.assertIn("Installed skill to ~/workspace-a/skills/pg-memo", proc.stdout)


if __name__ == "__main__":
    unittest.main()
