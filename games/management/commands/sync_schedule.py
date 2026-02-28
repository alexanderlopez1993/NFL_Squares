"""
Management command to sync the NFL schedule from ESPN.

Usage:
    python manage.py sync_schedule
    python manage.py sync_schedule --season 2025 --week 1
    python manage.py sync_schedule --postseason
    python manage.py sync_schedule --all-weeks
"""
from django.core.management.base import BaseCommand

from games.espn import fetch_scoreboard, upsert_game


class Command(BaseCommand):
    help = 'Sync NFL schedule from ESPN'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2025)
        parser.add_argument('--week', type=int)
        parser.add_argument('--postseason', action='store_true')
        parser.add_argument('--all-weeks', action='store_true',
                            help='Sync all 18 regular season weeks')

    def handle(self, *args, **options):
        season = options['season']
        postseason = options['postseason']
        all_weeks = options['all_weeks']
        week = options['week']

        if postseason:
            self._sync(season_type=3, season=season)
        elif all_weeks:
            for w in range(1, 19):
                self._sync(season_type=2, season=season, week=w)
        else:
            self._sync(season_type=2, season=season, week=week)

    def _sync(self, season_type, season, week=None):
        label = f"season={season}, type={season_type}" + (f", week={week}" if week else "")
        self.stdout.write(f'Syncing {label} ...')
        games = fetch_scoreboard(week=week, season=season, season_type=season_type)
        if not games:
            self.stdout.write(self.style.WARNING('  No games returned.'))
            return
        created_count = 0
        updated_count = 0
        for game_data in games:
            _, created = upsert_game(game_data)
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'  Done: {created_count} created, {updated_count} updated.'
        ))
