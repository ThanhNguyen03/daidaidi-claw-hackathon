#!/usr/bin/env bash
# GreenNode AgentBase IAM token helper
# Usage: TOKEN=$(bash .claude/skills/agentbase/scripts/get_token.sh)
# Caches token in .agentbase/token_cache, validates expiry via JWT exp claim.
# Pass --force to skip cache and fetch a new token.

set -euo pipefail

AGENTBASE_DIR=".agentbase"
CACHE_FILE="$AGENTBASE_DIR/token_cache"
SAFETY_MARGIN=60  # seconds before actual expiry to consider token stale

# Ensure .agentbase directory exists with restricted permissions
mkdir -p "$AGENTBASE_DIR"
chmod 700 "$AGENTBASE_DIR"

# Load credentials from .greennode.json if env vars not set
if [ -z "${GREENNODE_CLIENT_ID:-}" ] || [ -z "${GREENNODE_CLIENT_SECRET:-}" ]; then
  if [ -f ".greennode.json" ]; then
    GREENNODE_CLIENT_ID=$(python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path(".greennode.json").read_text(encoding="utf-8"))
print(data.get("client_id", ""))
PY
)
    GREENNODE_CLIENT_SECRET=$(python - <<'PY'
import json
from pathlib import Path
data = json.loads(Path(".greennode.json").read_text(encoding="utf-8"))
print(data.get("client_secret", ""))
PY
)
  fi
fi

if [ -z "${GREENNODE_CLIENT_ID:-}" ] || [ -z "${GREENNODE_CLIENT_SECRET:-}" ]; then
  echo "ERROR: GREENNODE_CLIENT_ID and GREENNODE_CLIENT_SECRET are required" >&2
  exit 1
fi

# Check cached token (skip if --force)
if [ "${1:-}" != "--force" ] && [ -f "$CACHE_FILE" ]; then
  cached_token=$(cat "$CACHE_FILE")
  # Decode JWT payload to check exp
  payload=$(echo "$cached_token" | cut -d. -f2 | \
    awk '{l=length($0)%4; if(l==2) $0=$0"=="; else if(l==3) $0=$0"="; print}' | \
    tr '_-' '/+')
  decoded=$(echo "$payload" | base64 -d 2>/dev/null || echo "$payload" | base64 -D 2>/dev/null || echo '{}')
  exp=$(DECODED_JSON="$decoded" python -c 'import json, os; print(json.loads(os.environ.get("DECODED_JSON", "{}") or "{}").get("exp", 0))')
  now=$(date +%s)
  if [[ "$exp" =~ ^[0-9]+$ ]] && [ "$exp" -gt "$((now + SAFETY_MARGIN))" ] 2>/dev/null; then
    echo "$cached_token"
    exit 0
  fi
fi

# Fetch new token
response=$(curl -s -X POST "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token" \
  -u "$GREENNODE_CLIENT_ID:$GREENNODE_CLIENT_SECRET" \
  -d "grant_type=client_credentials" \
  -H "Content-Type: application/x-www-form-urlencoded")

token=$(RESPONSE_JSON="$response" python -c 'import json, os; print(json.loads(os.environ.get("RESPONSE_JSON", "{}") or "{}").get("access_token", ""))')

if [ -z "$token" ]; then
  # Only show safe error info — never dump raw response (may contain credential-adjacent data)
  error_msg=$(RESPONSE_JSON="$response" python -c 'import json, os; data=json.loads(os.environ.get("RESPONSE_JSON", "{}") or "{}"); print(data.get("error") or data.get("message") or "")')
  if [ -n "$error_msg" ]; then
    echo "ERROR: Failed to fetch token: $error_msg" >&2
  else
    echo "ERROR: Failed to fetch token. Check credentials with: bash .claude/skills/agentbase/scripts/check_credentials.sh iam" >&2
  fi
  exit 1
fi

echo "$token" > "$CACHE_FILE"
echo "$token"
