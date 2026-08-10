# NFL Squares

A web app for running NFL squares pools. Built with Django, PostgreSQL, HTMX, and Tailwind CSS.

## Features

- Create 10×10 squares boards tied to any NFL game
- Participants claim squares by name (no account required)
- Commissioner marks payments in the Django admin
- Participants pick slots first; random scoring digits are assigned only when the commissioner locks the board
- Live scores synced from ESPN's unofficial API (the browser refreshes every 60 seconds during games)
- Quarter winners appear only after a period is complete; the final payout includes overtime
- Private, high-entropy board links with cache and referrer protections
- Commissioner ownership boundaries, claim limits, and a participant privacy notice

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up
docker compose exec web python manage.py createsuperuser
```

Compose runs Django against the `db` PostgreSQL service even though
`.env.example` defaults to SQLite for direct local development. Then visit
http://localhost:8000/admin to create a board.

Health checks:

```bash
docker compose ps
curl http://localhost:8000/healthz/
```

## Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build:css
# Set DB_HOST=localhost in .env, or set USE_SQLITE=True for local-only work
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For template/CSS work, run `npm run watch:css` in a second terminal while
developing. Production and Docker builds should run `npm run build:css` before
`python manage.py collectstatic`.

## Local Server Control

This repo includes a macOS launcher workflow for controlling local access:

- Desktop app: `~/Desktop/NFL Squares Control.app`
- Control script: `script/nfl_squares_server.sh`
- Local URL: `http://127.0.0.1:8000/boards/dashboard/`

The Desktop app can open the dashboard, start the local server, stop the local
server, and show status. Starting the server prompts for the local admin
password stored in macOS Keychain item `NFL Squares local admin`.

CLI controls:

```bash
script/nfl_squares_server.sh status
script/nfl_squares_server.sh stop
```

For scripted starts, provide the local admin password through
`NFL_SQUARES_ADMIN_PASSWORD`; the Desktop app handles that prompt for normal use.

## Public Test Sharing

The local Django server stays bound to `127.0.0.1`, so people outside your Mac
cannot reach it directly. For short test windows, use Cloudflare Tunnel:

```bash
# one-time install, if needed
brew install cloudflared

# starts the local server if needed, then prints a public trycloudflare.com URL
NFL_SQUARES_ADMIN_PASSWORD=... script/nfl_squares_public_share.sh start

# turn off public access
script/nfl_squares_public_share.sh stop
```

The Desktop app includes **Start Public Share** and **Stop Public Share**. Public
share links use the same tokenized board URLs as local links. The dashboard and
board index still require staff login; participant board links remain accessible
only to someone who has the board token. Use **Regenerate Link** on a board
before public sharing if it was created with a legacy short token. Stopping the
local server also stops the public tunnel.

For a stable public URL, replace the quick tunnel with a named Cloudflare Tunnel
and a custom hostname. Add that hostname to `ALLOWED_HOSTS`.

## Admin Login with Google OAuth

The admin login page supports Google OAuth through `django-allauth`.
Local username/password login remains available as a setup fallback.

1. Create a Google OAuth web client.
2. Add this redirect URI:

```text
http://localhost:8000/accounts/google/login/callback/
```

3. Set these values in `.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
ADMIN_OAUTH_STAFF_EMAILS=you@example.com
```

OAuth access is limited to an existing active staff user email or to
`ADMIN_OAUTH_STAFF_EMAILS` / `ADMIN_OAUTH_STAFF_DOMAINS`. Superuser access is
only granted by `ADMIN_OAUTH_SUPERUSER_EMAILS`.

## Syncing NFL Data

```bash
# Sync current week's schedule + scores
python manage.py sync_schedule

# Sync all 18 regular season weeks
python manage.py sync_schedule --all-weeks --season 2026

# Sync postseason (playoffs + Super Bowl)
python manage.py sync_schedule --postseason --season 2026

# Update live scores (run via cron every 5 min on game days)
python manage.py sync_scores
```

The production blueprint runs score sync every five minutes and schedule sync
daily. The ESPN feed is unofficial, so commissioners should follow the manual
score-recovery procedure in the operations runbook if it becomes unavailable.

## Commissioner Workflow

1. Run `sync_schedule` to import NFL games
2. In `/boards/dashboard/`, create a **Board** — pick a game, set entry fee and payout %s, add payment notes
3. Share the board URL with participants
4. Participants claim squares; mark them **paid** from the dashboard
5. Once everyone's in, open the board dashboard and run **Assign Numbers**
6. Scores update automatically during the game (or manually via `sync_scores`)

Use `/boards/dashboard/` for the commissioner workflow. Django admin remains
available for deeper maintenance. Local development defaults to Django's console
email backend so invites print to the terminal instead of sending real email.

## Deployment

Deployment is staged around CI, Docker, and explicit environment variables:

- Local and Docker smoke checks must pass before a remote deploy.
- CI runs Django tests against PostgreSQL and builds the Docker image.
- Manual container publishing is available through GitHub Actions.
- Environment templates live in `.env.dev.example` and `.env.prod.example`.
- `render.yaml` provisions the web service, PostgreSQL database, and sync jobs.

Use these documents for release:

- `docs/deployment/staged-deployment.md` — first deployment and rollback
- `docs/release-checklist.md` — exact go/no-go checklist
- `docs/operations/runbook.md` — game-day operations, recovery, and retention
