#!/usr/bin/env bash
# Check if credentials exist WITHOUT revealing their values.
# Usage:
#   bash .claude/skills/agentbase/scripts/check_credentials.sh iam
#   bash .claude/skills/agentbase/scripts/check_credentials.sh registry <path-to-credentials-file>
#   bash .claude/skills/agentbase/scripts/check_credentials.sh registry --credentials-file <path>
#   bash .claude/skills/agentbase/scripts/check_credentials.sh llm
#   bash .claude/skills/agentbase/scripts/check_credentials.sh aip  # alias for llm
#
# Exit code: 0 = found, 1 = missing
# stdout: status message (no secrets)

set -euo pipefail

json_get() {
  local file="$1"
  local key="$2"
  python - "$file" "$key" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    sys.exit(0)
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(0)
value = data.get(key, "")
if value:
    print(value)
PY
}

TYPE="${1:-}"

case "$TYPE" in
  iam)
    # Check environment variables first
    if [ -n "${GREENNODE_CLIENT_ID:-}" ] && [ -n "${GREENNODE_CLIENT_SECRET:-}" ]; then
      echo "OK: IAM credentials found in environment variables"
      exit 0
    fi
    # Check .greennode.json
    if [ -f ".greennode.json" ]; then
      cid=$(json_get ".greennode.json" "client_id")
      csec=$(json_get ".greennode.json" "client_secret")
      if [ -n "$cid" ] && [ -n "$csec" ]; then
        echo "OK: IAM credentials found in .greennode.json (client_id: ${cid:0:8}...)"
        exit 0
      fi
    fi
    echo "MISSING: IAM credentials not found. Set GREENNODE_CLIENT_ID and GREENNODE_CLIENT_SECRET as environment variables, or create .greennode.json with client_id and client_secret fields."
    exit 1
    ;;

  registry)
    creds_file="${2:-}"
    # Support both positional arg and --credentials-file flag
    if [ "$creds_file" = "--credentials-file" ]; then
      creds_file="${3:-}"
    fi
    if [ -z "$creds_file" ]; then
      echo "Usage: $0 registry <path-to-credentials-file>" >&2
      echo "       $0 registry --credentials-file <path>" >&2
      exit 2
    fi
    if [ -f "$creds_file" ]; then
      user=$(json_get "$creds_file" "username")
      pass=$(json_get "$creds_file" "password")
      reg=$(json_get "$creds_file" "registry")
      repo=$(json_get "$creds_file" "repository")
      if [ -n "$user" ] && [ -n "$pass" ]; then
        echo "OK: Registry credentials found in $creds_file"
        echo "  username:   $user"
        [ -n "$reg" ]  && echo "  registry:   $reg"
        [ -n "$repo" ] && echo "  repository: $repo"
        exit 0
      else
        echo "MISSING: $creds_file exists but username or password is empty"
        exit 1
      fi
    fi
    echo "MISSING: $creds_file not found. Create it using save_registry_credentials.sh --output $creds_file"
    exit 1
    ;;

  llm|aip)
    # Check LLM_API_KEY first (generic), then AIP_API_KEY (backward compat)
    if [ -n "${LLM_API_KEY:-}" ]; then
      echo "OK: LLM API key found in environment variable (LLM_API_KEY)"
      exit 0
    fi
    if [ -n "${AIP_API_KEY:-}" ]; then
      echo "OK: LLM API key found in environment variable (AIP_API_KEY)"
      exit 0
    fi
    # Check .env file
    if [ -f ".env" ]; then
      llm_key=$(grep -E '^LLM_API_KEY=' .env 2>/dev/null | cut -d= -f2-)
      if [ -n "$llm_key" ]; then
        echo "OK: LLM API key found in .env as LLM_API_KEY (length: ${#llm_key} chars)"
        exit 0
      fi
      aip_key=$(grep -E '^AIP_API_KEY=' .env 2>/dev/null | cut -d= -f2-)
      if [ -n "$aip_key" ]; then
        echo "OK: LLM API key found in .env as AIP_API_KEY (length: ${#aip_key} chars)"
        exit 0
      fi
    fi
    echo "MISSING: LLM API key not found. Set LLM_API_KEY (or AIP_API_KEY) as environment variable, or add it to .env file."
    exit 1
    ;;

  *)
    echo "Usage: $0 <iam|registry|llm|aip>" >&2
    exit 2
    ;;
esac
