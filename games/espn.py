"""
ESPN unofficial API client for NFL score/schedule data.

Endpoints used:
  Scoreboard (current week):  http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
  Scoreboard (specific week): ...scoreboard?week=N&seasontype=2&season=YYYY
  Postseason:                 ...scoreboard?seasontype=3&season=YYYY
"""
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD = 'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
TIMEOUT = getattr(settings, 'ESPN_REQUEST_TIMEOUT', 10)

# ESPN status → our status
STATUS_MAP = {
    'STATUS_SCHEDULED': 'scheduled',
    'STATUS_IN_PROGRESS': 'in_progress',
    'STATUS_HALFTIME': 'in_progress',
    'STATUS_END_PERIOD': 'in_progress',
    'STATUS_FINAL': 'final',
    'STATUS_FINAL_OVERTIME': 'final',
    'STATUS_POSTPONED': 'scheduled',
    'STATUS_CANCELED': 'scheduled',
    'STATUS_DELAYED': 'scheduled',
}


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error('ESPN API request failed: %s', e)
        return None


def _parse_competitor(comp):
    """Extract score info from a competitor dict."""
    linescores = comp.get('linescores', [])
    quarters = [int(ls.get('value', 0)) for ls in linescores]

    return {
        'team': comp['team'].get('displayName', ''),
        'abbr': comp['team'].get('abbreviation', ''),
        'home_away': comp.get('homeAway', 'home'),
        'score': int(comp.get('score', 0)) if comp.get('score') else None,
        'q1': quarters[0] if len(quarters) > 0 else None,
        'q2': quarters[1] if len(quarters) > 1 else None,
        'q3': quarters[2] if len(quarters) > 2 else None,
        'q4': quarters[3] if len(quarters) > 3 else None,
        'ot': quarters[4] if len(quarters) > 4 else None,
    }


def parse_event(event):
    """Parse a raw ESPN event dict into a normalized game dict."""
    status_obj = event.get('status', {})
    status_type = status_obj.get('type', {})
    espn_status = status_type.get('name', 'STATUS_SCHEDULED')
    our_status = STATUS_MAP.get(espn_status, 'scheduled')

    competitions = event.get('competitions', [{}])
    competitors = competitions[0].get('competitors', []) if competitions else []

    home = None
    away = None
    for comp in competitors:
        parsed = _parse_competitor(comp)
        if comp.get('homeAway') == 'home':
            home = parsed
        else:
            away = parsed

    if not home or not away:
        return None

    # Parse date
    date_str = event.get('date', '')
    try:
        game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        game_date = timezone.now()

    season_obj = event.get('season', {})
    week_obj = event.get('week', {})

    return {
        'espn_id': event.get('id', ''),
        'home_team': home['team'],
        'away_team': away['team'],
        'home_abbr': home['abbr'],
        'away_abbr': away['abbr'],
        'game_date': game_date,
        'week': week_obj.get('number'),
        'season': season_obj.get('year', 2025),
        'season_type': season_obj.get('type', 2),
        'status': our_status,
        'period': status_obj.get('period', 0),
        'display_clock': status_obj.get('displayClock', ''),
        'home_q1': home['q1'],
        'home_q2': home['q2'],
        'home_q3': home['q3'],
        'home_q4': home['q4'],
        'home_ot': home['ot'],
        'home_total': home['score'] if our_status != 'scheduled' else None,
        'away_q1': away['q1'],
        'away_q2': away['q2'],
        'away_q3': away['q3'],
        'away_q4': away['q4'],
        'away_ot': away['ot'],
        'away_total': away['score'] if our_status != 'scheduled' else None,
    }


def fetch_scoreboard(week=None, season=None, season_type=2):
    """
    Fetch game data from ESPN scoreboard.

    Returns a list of parsed game dicts, or [] on failure.
    """
    params = {'seasontype': season_type}
    if week:
        params['week'] = week
    if season:
        params['season'] = season

    data = _get(ESPN_SCOREBOARD, params=params)
    if not data:
        return []

    events = data.get('events', [])
    games = []
    for event in events:
        parsed = parse_event(event)
        if parsed and parsed['espn_id']:
            games.append(parsed)

    return games


def upsert_game(game_data):
    """
    Create or update an NFLGame from parsed game data.
    Returns (game, created) tuple.
    """
    from games.models import NFLGame

    espn_id = game_data.pop('espn_id')
    game_data['last_synced'] = timezone.now()

    game, created = NFLGame.objects.update_or_create(
        espn_id=espn_id,
        defaults=game_data,
    )
    return game, created
