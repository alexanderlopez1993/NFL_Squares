"""
Management command to sync live/recent scores from ESPN.

Designed to be run frequently (e.g., every 5 minutes via cron on game days).

Usage:
    python manage.py sync_scores
    python manage.py sync_scores --postseason
"""
from django.core.management.base import BaseCommand

from games.espn import fetch_scoreboard, upsert_game
from games.models import NFLGame


class Command(BaseCommand):
    help = 'Sync current NFL scores from ESPN scoreboard'

    def add_arguments(self, parser):
        parser.add_argument('--postseason', action='store_true',
                            help='Sync postseason games instead of regular season')

    def handle(self, *args, **options):
        season_type = 3 if options['postseason'] else 2

        self.stdout.write('Fetching current scoreboard from ESPN...')
        games = fetch_scoreboard(season_type=season_type)

        if not games:
            self.stdout.write(self.style.WARNING('No games returned from ESPN.'))
            return

        updated = 0
        for game_data in games:
            _, created = upsert_game(game_data)
            status = game_data.get('status', 'unknown')
            label = f"{game_data['away_abbr']} @ {game_data['home_abbr']}"
            tag = 'NEW' if created else status.upper()
            self.stdout.write(f'  [{tag}] {label}')
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Done. {updated} game(s) synced.'))
