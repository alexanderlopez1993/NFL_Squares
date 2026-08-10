from datetime import date
from io import StringIO
from unittest.mock import call, patch

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from .espn import (
    ESPN_SCOREBOARD,
    REQUEST_HEADERS,
    current_nfl_season,
    parse_event,
    upsert_game,
)
from .models import NFLGame


def make_game_data(espn_id='401-test-game'):
    """Build normalized ESPN game data for persistence tests.

    Args:
        espn_id (str): Identifier assigned to the normalized game.

    Returns:
        dict[str, object]: Complete payload accepted by ``upsert_game``.
    """
    return {
        'espn_id': espn_id,
        'home_team': 'Home Team',
        'away_team': 'Away Team',
        'home_abbr': 'HOM',
        'away_abbr': 'AWY',
        'game_date': timezone.now(),
        'week': 1,
        'season': 2026,
        'season_type': NFLGame.SEASON_TYPE_REGULAR,
        'status': NFLGame.STATUS_SCHEDULED,
        'espn_status': 'STATUS_SCHEDULED',
        'period': 0,
        'display_clock': '',
        'home_q1': None,
        'home_q2': None,
        'home_q3': None,
        'home_q4': None,
        'home_ot': None,
        'home_total': None,
        'away_q1': None,
        'away_q2': None,
        'away_q3': None,
        'away_q4': None,
        'away_ot': None,
        'away_total': None,
    }


class ESPNParsingTests(TestCase):
    """Tests ESPN transport assumptions and payload normalization.

    Args:
        None.

    Returns:
        None.
    """

    def test_scoreboard_transport_uses_https_without_spoofed_browser_headers(self):
        """Use ESPN over TLS without headers that its edge currently rejects.

        Args:
            None.

        Returns:
            None.
        """
        self.assertTrue(ESPN_SCOREBOARD.startswith('https://'))
        self.assertNotIn('Referer', REQUEST_HEADERS)
        self.assertNotIn('User-Agent', REQUEST_HEADERS)

    def test_current_season_handles_postseason_calendar_year(self):
        """Map January postseason games to the prior NFL season.

        Args:
            None.

        Returns:
            None.
        """
        self.assertEqual(current_nfl_season(date(2026, 1, 15)), 2025)
        self.assertEqual(current_nfl_season(date(2026, 8, 15)), 2026)

    def test_parse_event_sums_multiple_overtime_periods(self):
        """Combine every ESPN overtime line score into the stored OT value.

        Args:
            None.

        Returns:
            None.
        """
        event = {
            'id': '401-overtime',
            'date': '2026-01-15T01:00:00Z',
            'season': {'year': 2025, 'type': 3},
            'week': {'number': 20},
            'status': {
                'period': 6,
                'displayClock': '0:00',
                'type': {'name': 'STATUS_FINAL_OVERTIME'},
            },
            'competitions': [{
                'competitors': [
                    {
                        'homeAway': 'home',
                        'score': '29',
                        'team': {'displayName': 'Home Team', 'abbreviation': 'HOM'},
                        'linescores': [
                            {'value': 7}, {'value': 3}, {'value': 7}, {'value': 3},
                            {'value': 3}, {'value': 6},
                        ],
                    },
                    {
                        'homeAway': 'away',
                        'score': '26',
                        'team': {'displayName': 'Away Team', 'abbreviation': 'AWY'},
                        'linescores': [
                            {'value': 3}, {'value': 7}, {'value': 3}, {'value': 7},
                            {'value': 6}, {'value': 0},
                        ],
                    },
                ],
            }],
        }

        parsed = parse_event(event)

        self.assertEqual(parsed['home_ot'], 9)
        self.assertEqual(parsed['away_ot'], 6)
        self.assertEqual(parsed['home_total'], 29)
        self.assertEqual(parsed['away_total'], 26)
        self.assertEqual(parsed['status'], NFLGame.STATUS_FINAL)
        self.assertEqual(parsed['espn_status'], 'STATUS_FINAL_OVERTIME')

    def test_upsert_does_not_mutate_parsed_input(self):
        """Leave reusable parsed game data intact after database persistence.

        Args:
            None.

        Returns:
            None.
        """
        game_data = make_game_data()
        original = game_data.copy()

        game, created = upsert_game(game_data)

        self.assertTrue(created)
        self.assertEqual(game.espn_id, game_data['espn_id'])
        self.assertEqual(game_data, original)


class PayoutCheckpointTests(TestCase):
    """Tests completion gates for quarter payout scores.

    Args:
        None.

    Returns:
        None.
    """

    def test_current_quarter_score_is_not_treated_as_complete(self):
        """Hide a payout checkpoint while its quarter is still underway.

        Args:
            None.

        Returns:
            None.
        """
        game = NFLGame(
            status=NFLGame.STATUS_IN_PROGRESS,
            espn_status='STATUS_IN_PROGRESS',
            period=1,
            home_q1=7,
            away_q1=3,
        )

        self.assertEqual(game.scores_for_payout(1), (None, None))

    def test_end_period_and_halftime_unlock_completed_checkpoints(self):
        """Publish Q1 and halftime scores at confirmed ESPN boundaries.

        Args:
            None.

        Returns:
            None.
        """
        game = NFLGame(
            status=NFLGame.STATUS_IN_PROGRESS,
            espn_status='STATUS_END_PERIOD',
            period=1,
            home_q1=7,
            away_q1=3,
        )
        self.assertEqual(game.scores_for_payout(1), (7, 3))

        game.espn_status = 'STATUS_HALFTIME'
        game.period = 2
        game.home_q2 = 10
        game.away_q2 = 7

        self.assertEqual(game.scores_for_payout(2), (17, 10))

    def test_final_checkpoint_waits_for_official_final_status(self):
        """Avoid declaring the final payout during regulation or overtime.

        Args:
            None.

        Returns:
            None.
        """
        game = NFLGame(
            status=NFLGame.STATUS_IN_PROGRESS,
            espn_status='STATUS_IN_PROGRESS',
            period=5,
            home_q1=7,
            home_q2=3,
            home_q3=7,
            home_q4=3,
            away_q1=3,
            away_q2=7,
            away_q3=3,
            away_q4=7,
            home_total=23,
            away_total=20,
        )

        self.assertEqual(game.scores_for_payout(4), (None, None))

        game.status = NFLGame.STATUS_FINAL
        game.home_total = 26
        game.away_total = 23

        self.assertEqual(game.scores_for_payout(4), (26, 23))


class ScoreSyncCommandTests(TestCase):
    """Tests scheduled score synchronization command behavior.

    Args:
        None.

    Returns:
        None.
    """

    @patch('games.management.commands.sync_scores.upsert_game')
    @patch('games.management.commands.sync_scores.fetch_scoreboard')
    def test_default_sync_checks_regular_and_postseason_without_duplicates(
        self,
        mocked_fetch,
        mocked_upsert,
    ):
        """Fetch both season segments and persist each ESPN event once.

        Args:
            mocked_fetch (Mock): Patched scoreboard fetcher.
            mocked_upsert (Mock): Patched database persistence function.

        Returns:
            None.
        """
        game_data = make_game_data()
        mocked_fetch.side_effect = [[game_data], [game_data.copy()]]
        mocked_upsert.return_value = (object(), True)
        output = StringIO()

        call_command('sync_scores', stdout=output)

        self.assertEqual(
            mocked_fetch.call_args_list,
            [
                call(season_type=NFLGame.SEASON_TYPE_REGULAR),
                call(season_type=NFLGame.SEASON_TYPE_POSTSEASON),
            ],
        )
        mocked_upsert.assert_called_once_with(game_data)
        self.assertIn('1 game(s) synced', output.getvalue())

    @patch('games.management.commands.sync_scores.fetch_scoreboard', return_value=[])
    def test_fail_on_empty_supports_scheduler_alerting(self, mocked_fetch):
        """Exit non-zero when a monitored synchronization receives no games.

        Args:
            mocked_fetch (Mock): Patched scoreboard fetcher returning no data.

        Returns:
            None.
        """
        with self.assertRaises(CommandError):
            call_command('sync_scores', '--fail-on-empty')

        self.assertEqual(mocked_fetch.call_count, 2)
