"""
Management command to sync live/recent scores from ESPN.

Designed to be run frequently (e.g., every 5 minutes via cron on game days).

Usage:
    python manage.py sync_scores
    python manage.py sync_scores --season-type postseason
    python manage.py sync_scores --fail-on-empty
"""
from django.core.management.base import BaseCommand, CommandError

from games.espn import fetch_scoreboard, upsert_game
from games.models import NFLGame


class Command(BaseCommand):
    help = 'Sync current NFL scores from ESPN scoreboard'

    def add_arguments(self, parser):
        """Configure score synchronization command arguments.

        Args:
            parser (CommandParser): Django management command parser.

        Returns:
            None.
        """
        parser.add_argument(
            '--season-type',
            choices=['regular', 'postseason', 'both'],
            default='both',
            help='Scoreboard segment to sync; defaults to both.',
        )
        parser.add_argument('--postseason', action='store_true',
                            help='Deprecated alias for --season-type postseason')
        parser.add_argument(
            '--fail-on-empty',
            action='store_true',
            help='Exit non-zero when ESPN returns no games; useful for scheduled monitoring.',
        )

    def handle(self, *args, **options):
        """Fetch selected scoreboard segments and upsert unique games.

        Args:
            *args (object): Positional command arguments supplied by Django.
            **options (object): Parsed management command options.

        Returns:
            None.

        Raises:
            CommandError: If monitoring requires data and both scoreboards are empty.
        """
        selection = 'postseason' if options['postseason'] else options['season_type']
        season_types = {
            'regular': [NFLGame.SEASON_TYPE_REGULAR],
            'postseason': [NFLGame.SEASON_TYPE_POSTSEASON],
            'both': [NFLGame.SEASON_TYPE_REGULAR, NFLGame.SEASON_TYPE_POSTSEASON],
        }[selection]

        self.stdout.write('Fetching current scoreboard from ESPN...')
        games_by_id = {}
        for season_type in season_types:
            games = fetch_scoreboard(season_type=season_type)
            for game_data in games:
                games_by_id[game_data['espn_id']] = game_data

        if not games_by_id:
            message = 'No games returned from ESPN.'
            if options['fail_on_empty']:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
            return

        updated = 0
        for game_data in games_by_id.values():
            _, created = upsert_game(game_data)
            status = game_data.get('status', 'unknown')
            label = f"{game_data['away_abbr']} @ {game_data['home_abbr']}"
            tag = 'NEW' if created else status.upper()
            self.stdout.write(f'  [{tag}] {label}')
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Done. {updated} game(s) synced.'))
