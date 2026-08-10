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
    espn_status = models.CharField(max_length=40, blank=True)
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

    def scores_for_payout(self, quarter):
        """Return the official cumulative scores for a payout checkpoint.

        The fourth-quarter payout represents the final game result. Once ESPN
        marks a game final, its totals include every overtime period and are
        therefore authoritative over the four regulation line scores.

        Args:
            quarter (int): Payout checkpoint from 1 through 4.

        Returns:
            tuple[int | None, int | None]: Home and away cumulative scores, or
            ``None`` values until the checkpoint has been completed.

        Raises:
            ValueError: If the requested checkpoint is outside quarters 1–4.
        """
        if quarter not in range(1, 5):
            raise ValueError('Payout quarter must be between 1 and 4.')
        if quarter == 4:
            if self.is_final:
                return self.home_total, self.away_total
            return None, None
        checkpoint_complete = (
            self.is_final
            or self.period > quarter
            or (
                self.period == quarter
                and self.espn_status in {'STATUS_END_PERIOD', 'STATUS_HALFTIME'}
            )
        )
        if not checkpoint_complete:
            return None, None
        return self.home_score_after_q(quarter), self.away_score_after_q(quarter)

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
