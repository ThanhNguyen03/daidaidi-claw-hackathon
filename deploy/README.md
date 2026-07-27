# Deploy — team server `zah-28.123c.vn`

## Layout

```
Internet ──443──► nginx (host, Rocky 9)          TLS: *.123c.vn wildcard
                    ├── /      ──► 127.0.0.1:3000   frontend  (Next.js standalone)
                    └── /api/  ──► 127.0.0.1:8000   backend   (FastAPI, /api stripped)
```

Neither container is published on a public interface — `docker-compose.prod.yml`
binds both to `127.0.0.1`, so nginx is the only way in.

| | |
|---|---|
| Host | `118.102.2.128` — **SSH on port 2222**, not 22 |
| User | `zah19-team28` (sudo NOPASSWD) |
| App dir | `~/app` |
| Compose | `docker compose -f docker-compose.prod.yml` |
| nginx vhost | `/etc/nginx/conf.d/zah-28.conf` (copy of `deploy/nginx-zah-28.conf`) |
| Secrets | `~/app/backend/.env.production`, mode 600, **server-only** |

## Deploy

```bash
bash deploy/deploy.sh              # sync + rebuild changed layers + restart + verify
bash deploy/deploy.sh backend      # one service only
bash deploy/deploy.sh --no-build   # config-only change, skip docker build
bash deploy/deploy.sh --logs       # tail live logs
```

First-time setup on your machine:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_deploy -N ''
ssh-copy-id -p 2222 -i ~/.ssh/id_deploy zah19-team28@118.102.2.128
```

The script ships a tarball over SSH rather than having the server `git pull`,
because **the server cannot reach the internal GitLab host** — that connection
times out, while github.com resolves fine.

`backend/.env.production` is gitignored and never travels in the tarball; the
script also backs it up and restores it around extraction so a stray local copy
can't clobber the live key.

## CI

`.gitlab-ci.yml` runs the same `deploy/deploy.sh` from a runner, gated behind a
manual trigger. It needs a `DEPLOY_SSH_KEY` file variable and, critically, a
runner with outbound access to `118.102.2.128:2222` — run the
`deploy:check-reachability` job once to confirm before relying on it.

`.github/workflows/*` targets GreenNode AgentBase and is unrelated to this
server. It also can't fire: the git remote is GitLab, not GitHub.

## Runtime notes

- **`LLM_API_KEY`** in `.env.production` is a VNG Cloud MaaS key. Without a
  valid one the app boots and `/health` passes, but every LLM and embedding
  call returns 401 and the RAG index stays empty.
- **`FORWARDED_ALLOW_IPS=*`** is set so uvicorn trusts nginx's
  `X-Forwarded-For`. Without it every request looks like it comes from the
  docker bridge and slowapi's 10/min per-IP limit is shared by all users at once.
- **SSE** needs `proxy_buffering off` in the vhost; with buffering on, the chat
  appears frozen until the whole answer finishes.
- Build uses `backend/requirements-prod.txt` (no torch / sentence-transformers)
  via the `REQUIREMENTS` build arg — 1.3 GB image instead of ~4 GB. The local
  embedding fallback is therefore unavailable; production embeds via GreenNode.
- Persistent state lives in `~/app/data/backend` (SQLite sessions, LanceDB
  vectors, generated PPTX). It survives redeploys; delete it to reset a demo.
