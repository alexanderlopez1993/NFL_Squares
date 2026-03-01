"""
Management command to sync the NFL schedule from ESPN.

Usage:
    python manage.py sync_schedule                         # current week
    python manage.py sync_schedule --season 2025 --week 1 # specific week
    python manage.py sync_schedule --postseason            # all playoff rounds
    python manage.py sync_schedule --all-weeks             # full regular season
"""
from django.core.management.base import BaseCommand

from games.espn import fetch_scoreboard, fetch_postseason, upsert_game


class Command(BaseCommand):
    help = 'Sync NFL schedule from ESPN'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2025)
        parser.add_argument('--week', type=int)
        parser.add_argument('--postseason', action='store_true',
                            help='Sync all postseason rounds (Wild Card through Super Bowl)')
        parser.add_argument('--all-weeks', action='store_true',
                            help='Sync all 18 regular season weeks')

    def handle(self, *args, **options):
        season = options['season']
        postseason = options['postseason']
        all_weeks = options['all_weeks']
        week = options['week']

        if postseason:
            self._sync_postseason(season)
        elif all_weeks:
            for w in range(1, 19):
                self._sync(season_type=2, season=season, week=w)
        else:
            self._sync(season_type=2, season=season, week=week)

    def _sync_postseason(self, season):
        self.stdout.write(f'Syncing postseason for season={season} ...')
        self.stdout.write('  Using week-by-week (19-23) + date-range fallback ...')
        games = fetch_postseason(season)
        if not games:
            self.stdout.write(self.style.WARNING('  No postseason games returned.'))
            return
        self._upsert_games(games)

    def _sync(self, season_type, season, week=None):
        label = f"season={season}, type={season_type}" + (f", week={week}" if week else "")
        self.stdout.write(f'Syncing {label} ...')
        games = fetch_scoreboard(week=week, season=season, season_type=season_type)
        if not games:
            self.stdout.write(self.style.WARNING('  No games returned.'))
            return
        self._upsert_games(games)

    def _upsert_games(self, games):
        created_count = 0
        updated_count = 0
        for game_data in games:
            label = f"{game_data.get('away_abbr', '?')} @ {game_data.get('home_abbr', '?')}"
            _, created = upsert_game(game_data)
            if created:
                created_count += 1
                self.stdout.write(f'  [NEW] {label}')
            else:
                updated_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'  Done: {created_count} created, {updated_count} updated.'
        ))
