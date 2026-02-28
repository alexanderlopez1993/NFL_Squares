import random
import secrets
import string

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone


def _gen_token():
    return secrets.token_urlsafe(6)  # ~8 URL-safe chars


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
    access_token = models.CharField(max_length=12, unique=True, default=_gen_token, db_index=True)
    is_locked = models.BooleanField(default=False, help_text='Numbers have been assigned; no new claims allowed.')
    numbers_assigned_at = models.DateTimeField(null=True, blank=True)

    # Randomly assigned digits (lists of 0–9, None until locked)
    home_numbers = models.JSONField(null=True, blank=True)  # row axis = home team
    away_numbers = models.JSONField(null=True, blank=True)  # col axis = away team

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.game})"

    def get_absolute_url(self):
        return reverse('boards:detail', args=[self.access_token])

    # ------------------------------------------------------------------ #
    # Business logic
    # ------------------------------------------------------------------ #

    def assign_numbers(self):
        """Randomly assign 0–9 to each axis and lock the board."""
        nums = list(range(10))
        random.shuffle(nums)
        self.home_numbers = nums
        nums = list(range(10))
        random.shuffle(nums)
        self.away_numbers = nums
        self.is_locked = True
        self.numbers_assigned_at = timezone.now()
        self.save(update_fields=['home_numbers', 'away_numbers', 'is_locked', 'numbers_assigned_at'])

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

    def mark_paid(self, admin_user=None):
        self.paid = True
        self.paid_at = timezone.now()
        self.paid_by = admin_user
        self.save(update_fields=['paid', 'paid_at', 'paid_by'])
