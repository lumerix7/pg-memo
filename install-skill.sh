#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="pg-memo"
REQUIRED_FILES=(
  "$ROOT_DIR/SKILL.md"
  "$ROOT_DIR/README.md"
  "$ROOT_DIR/install.sh"
  "$ROOT_DIR/install-skill.sh"
  "$ROOT_DIR/scripts/pg-memo"
  "$ROOT_DIR/scripts/pg_memo.py"
  "$ROOT_DIR/sql/001_init.sql"
)

display_path() {
  local value="$1"
  if [[ "$value" == "$HOME"* ]]; then
    printf '~%s' "${value#$HOME}"
  else
    printf '%s' "$value"
  fi
}

resolve_default_targets() {
  if ! command -v openclaw >/dev/null 2>&1; then
    return 1
  fi
  if ! command -v jq >/dev/null 2>&1; then
    return 1
  fi

  openclaw agents list --json 2>/dev/null \
    | awk 'BEGIN {capture=0} /^\[$/ {capture=1} capture {print; if (/^\]$/) exit}' \
    | jq -r '.[].workspace + "/skills"' \
    | awk 'NF' \
    | sort -u
}

copy_skill() {
  local target_root="$1"
  local skill_root="$target_root/$SKILL_NAME"

  mkdir -p "$skill_root/scripts" "$skill_root/sql"
  install -m 644 "$ROOT_DIR/SKILL.md" "$skill_root/SKILL.md"
  install -m 644 "$ROOT_DIR/README.md" "$skill_root/README.md"
  install -m 755 "$ROOT_DIR/install.sh" "$skill_root/install.sh"
  install -m 755 "$ROOT_DIR/install-skill.sh" "$skill_root/install-skill.sh"
  install -m 755 "$ROOT_DIR/scripts/pg-memo" "$skill_root/scripts/pg-memo"
  install -m 644 "$ROOT_DIR/scripts/pg_memo.py" "$skill_root/scripts/pg_memo.py"
  install -m 644 "$ROOT_DIR/sql/001_init.sql" "$skill_root/sql/001_init.sql"
}

usage() {
  cat <<'USAGE'
Usage: ./install-skill.sh [options] [target ...]

Install the pg-memo skill into one or more OpenClaw workspace skills directories.

Options:
  -y, --yes     Skip confirmation prompt
  -h, --help    Show this help

Arguments:
  target        A skills directory to install into, for example: ~/my-workspace/skills

Notes:
  - If no targets are passed, the script tries to discover OpenClaw workspace skill directories.
  - Automatic discovery uses openclaw + jq when available.
USAGE
}

for required_path in "${REQUIRED_FILES[@]}"; do
  if [[ ! -e "$required_path" ]]; then
    echo "Missing required skill file: $required_path" >&2
    exit 1
  fi
done

AUTO_CONFIRM=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes)
      AUTO_CONFIRM=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

TARGETS=("$@")
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  mapfile -t TARGETS < <(resolve_default_targets || true)
fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "No skill targets provided, and no default OpenClaw workspaces could be resolved." >&2
  echo "Automatic discovery uses openclaw + jq when available." >&2
  echo "Pass explicit targets, for example:" >&2
  echo "  ./install-skill.sh ~/.openclaw/skills" >&2
  exit 1
fi

echo "Skill source: $(display_path "$ROOT_DIR")"
echo "Install targets:"
for target in "${TARGETS[@]}"; do
  echo "  - $(display_path "$target")"
done

if [[ $AUTO_CONFIRM -ne 1 ]]; then
  read -r -n 1 -p "Install pg-memo skill to these targets? [y/N] " reply
  echo
  if [[ ! "$reply" =~ [Yy] ]]; then
    echo "Aborted."
    exit 1
  fi
fi

for target in "${TARGETS[@]}"; do
  mkdir -p "$target"
  copy_skill "$target"
  echo "Installed skill to $(display_path "$target")/$SKILL_NAME"
done
