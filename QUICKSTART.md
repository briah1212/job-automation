# Quick Start

## Local (on your own machine)

```bash
git clone git@github.com:briah1212/job-automation.git
cd job-automation
./setup-portable.sh
```

This creates `.env` from `.env.example` with freshly generated random secrets
(if `.env` doesn't already exist), builds every image, and starts the full
stack.

Deploying to Hermes specifically (a persistent, already-logged-in remote
Chrome instance, not just "any remote server")? See [HERMES.md](./HERMES.md)
after this section - it covers the `BROWSER_CDP_URL` piece this doc doesn't.

## Remote server (e.g. a Hermes agent server)

Same as above, but pass the server's actual address so the frontend is built
to reach the API there instead of `localhost`:

```bash
git clone git@github.com:briah1212/job-automation.git
cd job-automation
./setup-portable.sh your-server-hostname-or-ip
```

If you need to change the public host later, edit `PUBLIC_HOST` (and
`NEXT_PUBLIC_API_URL`/`NEXTAUTH_URL`) in `.env`, then rebuild and restart:

```bash
docker compose build web
docker compose up -d web
```

(Rebuilding is required because `NEXT_PUBLIC_API_URL` is compiled into the
frontend's JavaScript bundle, not read at container startup.)

## Requirements

- Docker with the Compose plugin (`docker compose`), or Podman
- Git
- ~8GB RAM

No other external services or accounts are required - AI extraction runs in
`mock` mode by default (no API key needed), and Postgres/Redis/MinIO all run
in their own containers.

## Ports (defaults, overridable in `.env`)

- 3002 - Web frontend
- 8001 - API (+ `/docs` for interactive API docs)
- 8080 - Mock ATS (for testing the browser-automation flow end to end)
- 5432, 6379, 9000/9011 - Postgres / Redis / MinIO (bound to `127.0.0.1` only
  by default - see `INFRA_BIND` in `.env.example`)

## Next Steps

1. Register at `http://<host>:3002/auth/register`
2. Fill out your profile at `/dashboard/profile`
3. Upload a resume at `/dashboard/resumes`
4. Import a job (from the mock ATS at `http://<host>:8080`, or a real
   Greenhouse/Lever/Ashby posting) at `/dashboard/jobs`
5. Prepare and review the application, then start the browser submission
   from the application detail page

## Useful commands

```bash
docker compose logs -f            # tail all logs
docker compose logs -f api        # tail one service
docker compose down                # stop everything
docker compose down -v             # stop and wipe all data
make test                          # run backend + browser-worker + web tests
```
