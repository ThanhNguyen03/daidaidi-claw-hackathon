#!/usr/bin/env bash
# =============================================================================
# One-command deploy to the team server (zah-28.123c.vn)
# =============================================================================
#   bash deploy/deploy.sh                 # sync + rebuild changed images + restart
#   bash deploy/deploy.sh backend         # backend only
#   bash deploy/deploy.sh frontend        # frontend only
#   bash deploy/deploy.sh --no-build      # just sync source + restart (config edits)
#   bash deploy/deploy.sh --logs          # tail backend logs and exit
#
# Why push-over-SSH instead of a server-side `git pull`:
# the server cannot reach the internal GitLab host (connect times out), so the
# source has to be shipped from a machine that can see both.
#
# Override any of these via env vars:
#   SSH_HOST=118.102.2.128 SSH_PORT=2222 SSH_USER=zah19-team28 \
#   SSH_KEY=~/.ssh/id_deploy bash deploy/deploy.sh
set -euo pipefail

SSH_HOST="${SSH_HOST:-118.102.2.128}"
SSH_PORT="${SSH_PORT:-2222}"
SSH_USER="${SSH_USER:-zah19-team28}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_deploy}"
REMOTE_DIR="${REMOTE_DIR:-app}"
PUBLIC_URL="${PUBLIC_URL:-https://zah-28.123c.vn}"
COMPOSE="docker compose -f docker-compose.prod.yml"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SERVICE=""
DO_BUILD=1
for arg in "$@"; do
  case "$arg" in
    backend|frontend) SERVICE="$arg" ;;
    --no-build)       DO_BUILD=0 ;;
    --logs)           SERVICE="__logs__" ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

common_opts=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=25)
[ -f "$SSH_KEY" ] && common_opts+=(-i "$SSH_KEY")
# ssh takes -p for the port, scp takes -P. Keep two explicit arrays rather than
# rewriting one — a pattern substitution would also corrupt any path holding "-p".
ssh_opts=(-p "$SSH_PORT" "${common_opts[@]}")
scp_opts=(-P "$SSH_PORT" "${common_opts[@]}")
remote() { ssh "${ssh_opts[@]}" "$SSH_USER@$SSH_HOST" "$@"; }

if [ "$SERVICE" = "__logs__" ]; then
  remote "cd ~/$REMOTE_DIR && sudo $COMPOSE logs --tail=120 -f"
  exit 0
fi

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }

# --- 1. ship the source -------------------------------------------------------
say "Packing source"
TARBALL="$(mktemp -t adtimabox-deploy.XXXXXX).tgz"
trap 'rm -f "$TARBALL"' EXIT
tar --exclude='./.git' --exclude='node_modules' --exclude='.next' \
    --exclude='venv' --exclude='__pycache__' --exclude='./data' \
    --exclude='*.pyc' --exclude='./deploy/*.tgz' \
    -czf "$TARBALL" .
printf '    %s\n' "$(du -h "$TARBALL" | cut -f1)"

say "Uploading to $SSH_USER@$SSH_HOST:~/$REMOTE_DIR"
scp "${scp_opts[@]}" -q "$TARBALL" "$SSH_USER@$SSH_HOST:/tmp/deploy.tgz"

# .env.production holds the MaaS key and lives ONLY on the server — it is
# gitignored and absent from the tarball. Back it up anyway so a stray local
# copy can never overwrite the live one.
say "Extracting (preserving backend/.env.production)"
remote "set -e
  mkdir -p ~/$REMOTE_DIR/data/backend
  [ -f ~/$REMOTE_DIR/backend/.env.production ] && cp ~/$REMOTE_DIR/backend/.env.production /tmp/.env.keep || true
  tar -xzf /tmp/deploy.tgz -C ~/$REMOTE_DIR
  [ -f /tmp/.env.keep ] && mv /tmp/.env.keep ~/$REMOTE_DIR/backend/.env.production || true
  chmod 600 ~/$REMOTE_DIR/backend/.env.production 2>/dev/null || true
  rm -f /tmp/deploy.tgz"

# --- 2. build + restart -------------------------------------------------------
if [ "$DO_BUILD" -eq 1 ]; then
  say "Building${SERVICE:+ ($SERVICE)} — unchanged layers come from cache"
  remote "cd ~/$REMOTE_DIR && sudo $COMPOSE build $SERVICE"
fi

say "Restarting${SERVICE:+ ($SERVICE)}"
remote "cd ~/$REMOTE_DIR && sudo $COMPOSE up -d $SERVICE"

# --- 3. verify ----------------------------------------------------------------
say "Waiting for health"
remote "cd ~/$REMOTE_DIR && for i in \$(seq 1 30); do
    if curl -fsS -m 5 http://127.0.0.1:8000/health >/dev/null 2>&1 \
       && curl -fsS -m 5 http://127.0.0.1:3000/health >/dev/null 2>&1; then
      echo '    both services healthy'; break
    fi
    [ \$i -eq 30 ] && { echo '    TIMED OUT — recent logs:'; sudo $COMPOSE logs --tail=40; exit 1; }
    sleep 3
  done
  sudo $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}'"

say "Public check"
remote "curl -sk -o /dev/null -w '    frontend  %{http_code}\n' $PUBLIC_URL/
        curl -sk -w '    api       %{http_code}  ' -o /tmp/h -m 10 $PUBLIC_URL/api/health; cat /tmp/h; echo"

printf '\n\033[1;32m==> Deployed: %s\033[0m\n\n' "$PUBLIC_URL"
