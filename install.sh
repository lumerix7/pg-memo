#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
CONFIG_DIR="${HOME}/.config/pg-memo"
CONFIG_FILE="$CONFIG_DIR/config.json"
PASSWORD_FILE="$CONFIG_DIR/password"
BIN_DIR="${HOME}/.local/bin"
RUNTIME_DIR="${HOME}/.local/share/pg-memo"

DB_NAME="openclaw"
DB_USER="openclaw"
DB_HOST="127.0.0.1"
DB_PORT="5432"
YES=false
PASSWORD=""
PASSWORD_FILE_INPUT=""
FORCE_CONFIG=false
FORCE_PASSWORD=false

usage() {
  cat <<USAGE
Usage: ./install.sh [options]

Options:
  -y, --yes                   Skip confirmation prompts
      --bin-dir <path>        Install the pg-memo launcher to this directory
      --runtime-dir <path>    Install runtime files to this directory
      --password <value>      Set database password directly
      --password-file <path>  Read database password from file
  -d, --database <name>       Database name (default: openclaw)
  -u, --user <name>           Database user (default: openclaw)
  -h, --host <host>           Database host or IP (default: 127.0.0.1)
  -p, --port <port>           Database port (default: 5432)
      --force-config          Overwrite existing config file
      --force-password        Overwrite existing password file
      --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)
      YES=true; shift ;;
    --bin-dir)
      BIN_DIR="${2:-}"; shift 2 ;;
    --runtime-dir)
      RUNTIME_DIR="${2:-}"; shift 2 ;;
    --password)
      PASSWORD="${2:-}"; shift 2 ;;
    --password-file)
      PASSWORD_FILE_INPUT="${2:-}"; shift 2 ;;
    -d|--database)
      DB_NAME="${2:-}"; shift 2 ;;
    -u|--user)
      DB_USER="${2:-}"; shift 2 ;;
    -h|--host)
      DB_HOST="${2:-}"; shift 2 ;;
    -p|--port)
      DB_PORT="${2:-}"; shift 2 ;;
    --force-config)
      FORCE_CONFIG=true; shift ;;
    --force-password)
      FORCE_PASSWORD=true; shift ;;
    --help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

BIN_DIR="${BIN_DIR/#\~/$HOME}"
BIN_FILE="$BIN_DIR/pg-memo"
RUNTIME_DIR="${RUNTIME_DIR/#\~/$HOME}"
PYTHON_FILE="$RUNTIME_DIR/pg_memo.py"

echo "Planned pg-memo install settings:"
echo "- bin dir: $BIN_DIR"
echo "- bin file: $BIN_FILE"
echo "- runtime dir: $RUNTIME_DIR"
echo "- python file: $PYTHON_FILE"
echo "- config dir: $CONFIG_DIR"
echo "- config file: $CONFIG_FILE"
echo "- password file: $PASSWORD_FILE"
echo "- host: $DB_HOST"
echo "- port: $DB_PORT"
echo "- database: $DB_NAME"
echo "- user: $DB_USER"
if [ -n "$PASSWORD" ] || [ -n "$PASSWORD_FILE_INPUT" ]; then
  echo "- password input: provided"
else
  echo "- password input: not provided"
fi
echo "- force config overwrite: $FORCE_CONFIG"
echo "- force password overwrite: $FORCE_PASSWORD"

echo
if [ "$YES" = false ]; then
  printf 'Proceed? [y/N] '
  read -r CONFIRM
  case "$CONFIRM" in
    y|Y|yes|YES) ;;
    *)
      echo "Aborted."
      exit 0
      ;;
  esac
fi

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR" 2>/dev/null || true

mkdir -p "$BIN_DIR" "$RUNTIME_DIR"
install -m 644 "$REPO_ROOT/scripts/pg_memo.py" "$PYTHON_FILE"
cat > "$BIN_FILE" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="\$(cd -- "\$(dirname -- "\$0")" && pwd)"
exec python3 "\$SCRIPT_DIR/../share/pg-memo/pg_memo.py" "\$@"
EOF
chmod 755 "$BIN_FILE"
echo "Installed: $PYTHON_FILE"
echo "Installed: $BIN_FILE"

if [ -n "$PASSWORD_FILE_INPUT" ]; then
  PASSWORD="$(cat "$PASSWORD_FILE_INPUT")"
fi

if [ -z "$PASSWORD" ] && [ ! -f "$PASSWORD_FILE" ] && [ -t 0 ] && [ "$YES" = false ]; then
  printf 'Database password (input hidden, leave empty to skip): '
  read -r -s PASSWORD
  printf '\n'
fi

if [ ! -f "$CONFIG_FILE" ] || [ "$FORCE_CONFIG" = true ]; then
  cat > "$CONFIG_FILE" <<JSON
{
  "postgres": {
    "host": "${DB_HOST}",
    "port": ${DB_PORT},
    "database": "${DB_NAME}",
    "user": "${DB_USER}",
    "passwordFile": "~/.config/pg-memo/password"
  },
  "defaults": {
    "scope": "main",
    "recentLimit": 10,
    "searchLimit": 10
  }
}
JSON
  chmod 600 "$CONFIG_FILE" 2>/dev/null || true
  echo "Wrote:   $CONFIG_FILE"
else
  echo "Exists:  $CONFIG_FILE"
  echo "Config file already exists; keeping current value. Use --force-config to overwrite."
fi

if [ -n "$PASSWORD" ]; then
  if [ -f "$PASSWORD_FILE" ] && [ "$FORCE_PASSWORD" = false ]; then
    echo "Exists:  $PASSWORD_FILE"
    echo "Password file already exists; keeping current value. Use --force-password to overwrite."
  else
    printf '%s' "$PASSWORD" > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE" 2>/dev/null || true
    echo "Wrote:   $PASSWORD_FILE"
  fi
elif [ ! -f "$PASSWORD_FILE" ]; then
  touch "$PASSWORD_FILE"
  chmod 600 "$PASSWORD_FILE" 2>/dev/null || true
  echo "Created: $PASSWORD_FILE"
  echo "Add the database password to this file before using pg-memo."
else
  echo "Exists:  $PASSWORD_FILE"
fi

if python3 -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("psycopg") or importlib.util.find_spec("psycopg2") else 1)' >/dev/null 2>&1; then
  echo "Python PostgreSQL driver: available"
else
  echo "Python PostgreSQL driver: not found"
  echo "Install with: sudo apt install python3-psycopg"
fi

echo
echo "Settings:"
echo "- bin file:   $BIN_FILE"
echo "- python file: $PYTHON_FILE"
echo "- host:      $DB_HOST"
echo "- port:      $DB_PORT"
echo "- database:  $DB_NAME"
echo "- user:      $DB_USER"

echo
echo "Next steps:"
echo "1. Use the installed command: $BIN_FILE"
echo "2. Review config: $CONFIG_FILE"
echo "3. Ensure a PostgreSQL client library is installed for Python (Ubuntu/Debian: sudo apt install python3-psycopg)"
echo "4. Ensure $BIN_DIR is on PATH if you want to run: pg-memo"
echo "5. Test: $BIN_FILE config"
echo "6. Test: $BIN_FILE recent --limit 5"
