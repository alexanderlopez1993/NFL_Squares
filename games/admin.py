from django.contrib import admin
from django.utils import timezone
from django.contrib import messages

from .models import NFLGame
from .espn import fetch_scoreboard, upsert_game


def sync_scores_action(modeladmin, request, queryset):
    """Admin action: sync scores from ESPN for selected games."""
    updated = 0
    # Pull current scoreboard (handles in-progress + recent finals)
    for season_type in [2, 3]:
        games = fetch_scoreboard(season_type=season_type)
        espn_ids = {g['espn_id'] for g in games}
        selected_ids = set(queryset.values_list('espn_id', flat=True))
        for game_data in games:
            if game_data['espn_id'] in selected_ids:
                upsert_game(game_data)
                updated += 1

    messages.success(request, f'Synced {updated} game(s) from ESPN.')


sync_scores_action.short_description = 'Sync scores from ESPN'


@admin.register(NFLGame)
class NFLGameAdmin(admin.ModelAdmin):
    list_display = [
        'away_abbr', 'home_abbr', 'game_date', 'week', 'season',
        'status', 'score_display', 'last_synced',
    ]
    list_filter = ['status', 'season', 'season_type']
    search_fields = ['home_team', 'away_team', 'espn_id']
    readonly_fields = ['espn_id', 'last_synced']
    ordering = ['-game_date']
    actions = [sync_scores_action]

    fieldsets = [
        ('Game Info', {
            'fields': ['espn_id', 'home_team', 'home_abbr', 'away_team', 'away_abbr',
                       'game_date', 'week', 'season', 'season_type'],
        }),
        ('Status', {
            'fields': ['status', 'period', 'display_clock', 'last_synced'],
        }),
        ('Home Scores', {
            'fields': ['home_q1', 'home_q2', 'home_q3', 'home_q4', 'home_ot', 'home_total'],
        }),
        ('Away Scores', {
            'fields': ['away_q1', 'away_q2', 'away_q3', 'away_q4', 'away_ot', 'away_total'],
        }),
    ]
