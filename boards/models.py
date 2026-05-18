import secrets

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


def _gen_token():
    """Generate a high-entropy board access token.

    Args:
        None.

    Returns:
        str: URL-safe token for private board links.
    """
    return secrets.token_urlsafe(16)


class Board(models.Model):
    game = models.ForeignKey(
        'games.NFLGame', on_delete=models.CASCADE, related_name='boards'
    )
    name = models.CharField(max_length=120)
    entry_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True, help_text='Instructions shown to participants (payment info, Venmo, etc.)')

    # Payouts as % of total paid pot — must sum to 100
    payout_q1_pct = models.PositiveSmallIntegerField(default=25)
    payout_q2_pct = models.PositiveSmallIntegerField(default=25)
    payout_q3_pct = models.PositiveSmallIntegerField(default=25)
    payout_q4_pct = models.PositiveSmallIntegerField(default=25)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Board state
    access_token = models.CharField(max_length=32, unique=True, default=_gen_token, db_index=True)
    is_locked = models.BooleanField(default=False, help_text='Numbers have been assigned; no new claims allowed.')
    numbers_assigned_at = models.DateTimeField(null=True, blank=True)

    # Randomly assigned digits (lists of 0–9, None until locked)
    home_numbers = models.JSONField(null=True, blank=True)  # row axis = home team
    away_numbers = models.JSONField(null=True, blank=True)  # col axis = away team

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.game})"

    def clean(self):
        """Validate board settings before saving.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValidationError: If payout percentages do not total 100.
        """
        super().clean()
        payout_total = (
            self.payout_q1_pct
            + self.payout_q2_pct
            + self.payout_q3_pct
            + self.payout_q4_pct
        )
        if payout_total != 100:
            raise ValidationError({
                '__all__': f'Payout percentages must total 100. Current total: {payout_total}.'
            })

    def get_absolute_url(self):
        return reverse('boards:detail', args=[self.access_token])

    # ------------------------------------------------------------------ #
    # Business logic
    # ------------------------------------------------------------------ #

    def assign_numbers(self):
        """Randomly assign scoring digits to each axis and lock the board.

        Args:
            None.

        Returns:
            None.
        """
        rng = secrets.SystemRandom()
        home_nums = list(range(10))
        away_nums = list(range(10))
        rng.shuffle(home_nums)
        rng.shuffle(away_nums)
        self.home_numbers = home_nums
        self.away_numbers = away_nums
        self.is_locked = True
        self.numbers_assigned_at = timezone.now()
        self.save(update_fields=['home_numbers', 'away_numbers', 'is_locked', 'numbers_assigned_at'])

    def regenerate_access_token(self):
        """Rotate the private board link token.

        Args:
            None.

        Returns:
            str: Newly saved access token.

        Raises:
            RuntimeError: If a unique token cannot be generated after repeated attempts.
        """
        for _ in range(10):
            token = _gen_token()
            exists = Board.objects.filter(access_token=token).exclude(pk=self.pk).exists()
            if not exists:
                self.access_token = token
                self.save(update_fields=['access_token'])
                return token
        raise RuntimeError('Could not generate a unique board access token.')

    @property
    def claimed_count(self):
        return self.squares.exclude(name='').count()

    @property
    def paid_count(self):
        return self.squares.filter(paid=True).count()

    @property
    def total_pot(self):
        from decimal import Decimal
        return self.paid_count * self.entry_fee

    def payout_for_quarter(self, q):
        pct = getattr(self, f'payout_q{q}_pct')
        return self.total_pot * pct / 100

    def winning_cell_for_quarter(self, q):
        """
        Returns (row, col) of the winning square at end of quarter q, or None.
        Requires the board to be locked and enough quarter scores to exist.
        """
        if not self.is_locked or not self.home_numbers:
            return None
        home_score = self.game.home_score_after_q(q)
        away_score = self.game.away_score_after_q(q)
        if home_score is None or away_score is None:
            return None
        home_digit = home_score % 10
        away_digit = away_score % 10
        try:
            row = self.home_numbers.index(home_digit)
            col = self.away_numbers.index(away_digit)
            return (row, col)
        except ValueError:
            return None

    def quarter_results(self):
        """Return a list of result dicts for each completed quarter."""
        results = []
        squares_by_pos = {(s.row, s.col): s for s in self.squares.all()}
        for q in range(1, 5):
            cell = self.winning_cell_for_quarter(q)
            if cell is None:
                continue
            row, col = cell
            home_score = self.game.home_score_after_q(q)
            away_score = self.game.away_score_after_q(q)
            results.append({
                'quarter': q,
                'home_score': home_score,
                'away_score': away_score,
                'home_digit': home_score % 10,
                'away_digit': away_score % 10,
                'winning_square': squares_by_pos.get((row, col)),
                'payout': self.payout_for_quarter(q),
            })
        return results


class Square(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='squares')
    row = models.PositiveSmallIntegerField()  # 0–9, home-team axis
    col = models.PositiveSmallIntegerField()  # 0–9, away-team axis

    # Claimant — no account required
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    # Payment tracking (admin marks this)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confirmed_payments',
    )

    class Meta:
        unique_together = [('board', 'row', 'col')]
        ordering = ['row', 'col']

    def __str__(self):
        label = self.name or 'unclaimed'
        return f"({self.row},{self.col}) {label} — {self.board.name}"

    @property
    def is_claimed(self):
        return bool(self.name)

    @property
    def grid_label(self):
        """Return the participant-facing square label.

        Args:
            None.

        Returns:
            str: Neutral grid label that does not reveal final scoring digits.
        """
        return f'{chr(65 + self.col)}{self.row + 1}'

    def mark_paid(self, admin_user=None):
        self.paid = True
        self.paid_at = timezone.now()
        self.paid_by = admin_user
        self.save(update_fields=['paid', 'paid_at', 'paid_by'])
