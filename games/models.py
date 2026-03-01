from django.db import models
from django.utils import timezone


class NFLGame(models.Model):
    SEASON_TYPE_REGULAR = 2
    SEASON_TYPE_POSTSEASON = 3

    STATUS_SCHEDULED = 'scheduled'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_FINAL = 'final'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_FINAL, 'Final'),
    ]

    espn_id = models.CharField(max_length=20, unique=True, db_index=True)
    home_team = models.CharField(max_length=60)
    away_team = models.CharField(max_length=60)
    home_abbr = models.CharField(max_length=6)
    away_abbr = models.CharField(max_length=6)

    game_date = models.DateTimeField()
    week = models.IntegerField(null=True, blank=True)
    season = models.IntegerField()
    season_type = models.IntegerField(default=SEASON_TYPE_REGULAR)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    period = models.IntegerField(default=0)  # current quarter/period
    display_clock = models.CharField(max_length=10, blank=True)

    # Per-quarter scores (None = not yet played)
    home_q1 = models.IntegerField(null=True, blank=True)
    home_q2 = models.IntegerField(null=True, blank=True)
    home_q3 = models.IntegerField(null=True, blank=True)
    home_q4 = models.IntegerField(null=True, blank=True)
    home_ot = models.IntegerField(null=True, blank=True)
    home_total = models.IntegerField(null=True, blank=True)

    away_q1 = models.IntegerField(null=True, blank=True)
    away_q2 = models.IntegerField(null=True, blank=True)
    away_q3 = models.IntegerField(null=True, blank=True)
    away_q4 = models.IntegerField(null=True, blank=True)
    away_ot = models.IntegerField(null=True, blank=True)
    away_total = models.IntegerField(null=True, blank=True)

    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['game_date']
        verbose_name = 'NFL Game'
        verbose_name_plural = 'NFL Games'

    def __str__(self):
        return f"{self.away_abbr} @ {self.home_abbr} ({self.game_date.strftime('%m/%d/%Y')})"

    def home_score_after_q(self, q):
        """Cumulative home score at end of quarter q (1–4)."""
        total = 0
        for i in range(1, q + 1):
            val = getattr(self, f'home_q{i}')
            if val is None:
                return None
            total += val
        return total

    def away_score_after_q(self, q):
        """Cumulative away score at end of quarter q (1–4)."""
        total = 0
        for i in range(1, q + 1):
            val = getattr(self, f'away_q{i}')
            if val is None:
                return None
            total += val
        return total

    @property
    def is_active(self):
        return self.status == self.STATUS_IN_PROGRESS

    @property
    def is_final(self):
        return self.status == self.STATUS_FINAL

    @property
    def score_display(self):
        if self.home_total is None:
            return 'vs'
        return f"{self.away_total} – {self.home_total}"
