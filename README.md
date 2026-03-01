# NFL Squares

A web app for running NFL squares pools. Built with Django, PostgreSQL, HTMX, and Tailwind CSS.

## Features

- Create 10×10 squares boards tied to any NFL game
- Participants claim squares by name (no account required)
- Commissioner marks payments in the Django admin
- Random number assignment locks the board
- Live scores synced from ESPN's unofficial API (auto-refreshes every 60s during games)
- Quarter-by-quarter winner display with payout calculations

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up
docker compose exec web python manage.py createsuperuser
```

Then visit http://localhost:8000/admin to create a board.

## Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Set DB_HOST=localhost in .env (or use SQLite by editing settings.py)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Syncing NFL Data

```bash
# Sync current week's schedule + scores
python manage.py sync_schedule

# Sync all 18 regular season weeks
python manage.py sync_schedule --all-weeks --season 2025

# Sync postseason (playoffs + Super Bowl)
python manage.py sync_schedule --postseason --season 2025

# Update live scores (run via cron every 5 min on game days)
python manage.py sync_scores
```

### Cron example (every 5 minutes)
```
*/5 * * * * cd /app && python manage.py sync_scores >> /var/log/sync_scores.log 2>&1
```

## Commissioner Workflow

1. Run `sync_schedule` to import NFL games
2. In `/admin`, create a **Board** — pick a game, set entry fee and payout %s, add payment notes
3. Share the board URL with participants
4. Participants claim squares; mark them **paid** in admin → `Squares`
5. Once everyone's in, select the board in admin and run **Assign numbers and lock**
6. Scores update automatically during the game (or manually via `sync_scores`)
