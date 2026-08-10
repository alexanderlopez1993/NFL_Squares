from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from games.models import NFLGame

from .admin import BoardAdmin, SquareAdmin
from .forms import ClaimSquaresForm
from .models import Board, Square


def make_game():
    """Create a valid NFL game for board tests.

    Args:
        None.

    Returns:
        NFLGame: Persisted game instance.
    """
    return NFLGame.objects.create(
        espn_id='401-test-game',
        home_team='Home Team',
        away_team='Away Team',
        home_abbr='HOM',
        away_abbr='AWY',
        game_date=timezone.now() + timedelta(days=1),
        week=1,
        season=2026,
    )


class BoardValidationTests(TestCase):
    """Tests board-level validation rules.

    Args:
        None.

    Returns:
        None.
    """

    def test_payout_percentages_must_total_100(self):
        """Reject payout schedules that do not total 100 percent.

        Args:
            None.

        Returns:
            None.
        """
        board = Board(
            game=make_game(),
            name='Invalid Payouts',
            payout_q1_pct=25,
            payout_q2_pct=25,
            payout_q3_pct=25,
            payout_q4_pct=10,
        )

        with self.assertRaises(ValidationError):
            board.full_clean()

    def test_assign_numbers_locks_board_with_digit_permutations(self):
        """Assign hidden scoring digits only when the board is locked.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Randomized Board')

        self.assertFalse(board.is_locked)
        self.assertIsNone(board.home_numbers)
        self.assertIsNone(board.away_numbers)

        board.assign_numbers()

        self.assertTrue(board.is_locked)
        self.assertEqual(sorted(board.home_numbers), list(range(10)))
        self.assertEqual(sorted(board.away_numbers), list(range(10)))
        self.assertIsNotNone(board.numbers_assigned_at)

    def test_access_tokens_are_long_enough_for_public_sharing(self):
        """Generate high-entropy token links for boards.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Secure Token Board')

        self.assertGreaterEqual(len(board.access_token), 20)

    def test_regenerate_access_token_rotates_legacy_link(self):
        """Replace a short board token with a stronger private link.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(),
            name='Legacy Token Board',
            access_token='legacy1',
        )

        new_token = board.regenerate_access_token()

        self.assertNotEqual(new_token, 'legacy1')
        self.assertGreaterEqual(len(new_token), 20)


class BoardAccessTests(TestCase):
    """Tests board visibility rules.

    Args:
        None.

    Returns:
        None.
    """

    def test_board_list_requires_staff_but_token_detail_is_public(self):
        """Keep the board index private while token links remain shareable.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Private Index Board')

        list_response = self.client.get(reverse('boards:list'))
        detail_response = self.client.get(board.get_absolute_url())

        self.assertEqual(list_response.status_code, 302)
        self.assertIn('/admin/login/', list_response.url)
        self.assertEqual(detail_response.status_code, 200)

    def test_staff_user_can_view_board_list(self):
        """Allow staff users to manage the board index.

        Args:
            None.

        Returns:
            None.
        """
        User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='password',
            is_staff=True,
        )
        self.client.login(username='staff', password='password')

        response = self.client.get(reverse('boards:list'))

        self.assertEqual(response.status_code, 200)


class AdminOwnershipTests(TestCase):
    """Tests commissioner data isolation in Django admin.

    Args:
        None.

    Returns:
        None.
    """

    def setUp(self):
        """Create commissioners and owned board records.

        Args:
            None.

        Returns:
            None.
        """
        self.request_factory = RequestFactory()
        self.owner = User.objects.create_user(
            username='owner', password='password', is_staff=True,
        )
        self.other_owner = User.objects.create_user(
            username='other-owner', password='password', is_staff=True,
        )
        game = make_game()
        self.owner_board = Board.objects.create(
            game=game, name='Owner Board', created_by=self.owner,
        )
        self.other_board = Board.objects.create(
            game=game, name='Other Board', created_by=self.other_owner,
        )
        self.owner_square = Square.objects.create(
            board=self.owner_board, row=0, col=0, name='Owner Player',
        )
        self.other_square = Square.objects.create(
            board=self.other_board, row=0, col=0, name='Other Player',
        )

    def test_board_admin_only_lists_the_commissioners_boards(self):
        """Hide boards owned by other commissioners.

        Args:
            None.

        Returns:
            None.
        """
        request = self.request_factory.get('/admin/boards/board/')
        request.user = self.owner

        queryset = BoardAdmin(Board, admin.site).get_queryset(request)

        self.assertQuerySetEqual(queryset, [self.owner_board])

    def test_square_admin_only_lists_squares_on_owned_boards(self):
        """Hide participant records from other commissioners.

        Args:
            None.

        Returns:
            None.
        """
        request = self.request_factory.get('/admin/boards/square/')
        request.user = self.owner

        queryset = SquareAdmin(Square, admin.site).get_queryset(request)

        self.assertQuerySetEqual(queryset, [self.owner_square])

    def test_superuser_can_list_all_boards_and_squares(self):
        """Retain global support access for superusers.

        Args:
            None.

        Returns:
            None.
        """
        superuser = User.objects.create_superuser(
            username='support', email='support@example.com', password='password',
        )
        request = self.request_factory.get('/admin/')
        request.user = superuser

        board_queryset = BoardAdmin(Board, admin.site).get_queryset(request)
        square_queryset = SquareAdmin(Square, admin.site).get_queryset(request)

        self.assertEqual(set(board_queryset), {self.owner_board, self.other_board})
        self.assertEqual(set(square_queryset), {self.owner_square, self.other_square})


class ClaimSquaresTests(TestCase):
    """Tests participant square claim behavior.

    Args:
        None.

    Returns:
        None.
    """

    def test_form_deduplicates_selected_squares(self):
        """Parse repeated square coordinates only once.

        Args:
            None.

        Returns:
            None.
        """
        form = ClaimSquaresForm(data={
            'name': 'Alex',
            'email': '',
            'squares': '1,2;1,2;3,4',
            'privacy_acknowledged': True,
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['squares'], [(1, 2), (3, 4)])

    def test_claim_does_not_overwrite_existing_claimant(self):
        """Skip already claimed squares while accepting available selections.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Claim Board')
        Square.objects.create(board=board, row=1, col=2, name='Existing')

        response = self.client.post(
            reverse('boards:claim', args=[board.access_token]),
            data={
                'name': 'New Player',
                'email': 'new@example.com',
                'squares': '1,2;3,4',
                'privacy_acknowledged': True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Square.objects.get(board=board, row=1, col=2).name, 'Existing')
        self.assertEqual(Square.objects.get(board=board, row=3, col=4).name, 'New Player')

    def test_claim_form_uses_neutral_slot_labels(self):
        """Avoid presenting pick coordinates as final scoring digits.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Neutral Labels')

        response = self.client.get(reverse('boards:claim', args=[board.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pick slots; scoring numbers are assigned after lock')
        self.assertContains(response, '>A</th>')
        self.assertNotContains(response, '>0</th>')

    def test_claim_grid_uses_accessible_slot_buttons(self):
        """Render available squares as keyboard-accessible toggle buttons.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Accessible Claims')

        response = self.client.get(reverse('boards:claim', args=[board.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Select slot A1"')
        self.assertContains(response, 'aria-pressed="false"')
        self.assertContains(response, 'id="submit-btn" disabled')
        self.assertContains(response, 'id="mobile-submit-btn"')
        self.assertContains(response, 'form="claim-form"')

    def test_claim_requires_privacy_acknowledgement(self):
        """Require participants to acknowledge the board's visibility rules.

        Args:
            None.

        Returns:
            None.
        """
        form = ClaimSquaresForm(data={
            'name': 'Alex',
            'email': 'alex@example.com',
            'squares': '1,2',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('privacy_acknowledged', form.errors)

    def test_claim_honeypot_rejects_automated_submission(self):
        """Reject a claim when the hidden bot-trap field is populated.

        Args:
            None.

        Returns:
            None.
        """
        form = ClaimSquaresForm(data={
            'name': 'Robot',
            'email': 'robot@example.com',
            'squares': '1,2',
            'privacy_acknowledged': True,
            'website': 'https://spam.example',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('website', form.errors)

    @override_settings(MAX_SQUARES_PER_PARTICIPANT=2, CLAIM_COOLDOWN_SECONDS=0)
    def test_claim_limit_applies_across_multiple_submissions(self):
        """Enforce the per-board participant cap across repeat claims.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Limited Claims')
        claim_url = reverse('boards:claim', args=[board.access_token])
        common_data = {
            'name': 'Limited Player',
            'email': 'limited@example.com',
            'privacy_acknowledged': True,
        }

        self.client.post(claim_url, data={**common_data, 'squares': '0,0;0,1'})
        response = self.client.post(claim_url, data={**common_data, 'squares': '0,2'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            board.squares.filter(email__iexact='limited@example.com').exclude(name='').count(),
            2,
        )
        self.assertFalse(board.squares.get(row=0, col=2).is_claimed)

    @override_settings(CLAIM_COOLDOWN_SECONDS=60)
    def test_claim_cooldown_rejects_immediate_repeat_submission(self):
        """Throttle immediate repeat claims from the same browser session.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Cooldown Claims')
        claim_url = reverse('boards:claim', args=[board.access_token])
        claim_data = {
            'name': 'Fast Player',
            'email': 'fast@example.com',
            'privacy_acknowledged': True,
        }

        self.client.post(claim_url, data={**claim_data, 'squares': '0,0'})
        response = self.client.post(claim_url, data={**claim_data, 'squares': '0,1'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(board.squares.filter(row=0, col=1, name='Fast Player').exists())

    def test_private_board_pages_disable_caching_and_referrers(self):
        """Apply privacy response headers to tokenized participant pages.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Private Headers')

        response = self.client.get(board.get_absolute_url())

        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')


class BoardScoringTests(TestCase):
    """Tests winner calculations against official game totals.

    Args:
        None.

    Returns:
        None.
    """

    def test_final_winner_uses_overtime_total(self):
        """Use the final total rather than the regulation score for Q4 payout.

        Args:
            None.

        Returns:
            None.
        """
        game = make_game()
        game.status = NFLGame.STATUS_FINAL
        game.home_q1 = 7
        game.home_q2 = 3
        game.home_q3 = 7
        game.home_q4 = 3
        game.home_ot = 6
        game.home_total = 26
        game.away_q1 = 3
        game.away_q2 = 7
        game.away_q3 = 3
        game.away_q4 = 7
        game.away_ot = 3
        game.away_total = 23
        game.save()
        board = Board.objects.create(
            game=game,
            name='Overtime Board',
            is_locked=True,
            home_numbers=list(range(10)),
            away_numbers=list(range(10)),
        )

        self.assertEqual(board.winning_cell_for_quarter(4), (6, 3))


class AdminLoginTests(TestCase):
    """Tests admin login page OAuth affordances.

    Args:
        None.

    Returns:
        None.
    """

    def test_admin_login_shows_google_oauth_button(self):
        """Render the Google OAuth entry point on the admin login page.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get(reverse('admin:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Google')

    def test_unconfigured_google_oauth_redirects_to_admin_login(self):
        """Avoid a server error before Google OAuth credentials are configured.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get('/accounts/google/login/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:login'))


class SiteChromeTests(TestCase):
    """Tests site-level shared browser chrome.

    Args:
        None.

    Returns:
        None.
    """

    def test_favicon_legacy_path_redirects_to_static_svg(self):
        """Redirect legacy favicon requests to the tracked SVG asset.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get('/favicon.ico')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, '/static/favicon.svg')

    @override_settings(DATA_RETENTION_DAYS=30, PRIVACY_CONTACT_EMAIL='privacy@example.com')
    def test_privacy_notice_explains_participant_visibility(self):
        """Publish participant data handling and contact information.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get(reverse('privacy'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'visible to anyone who has')
        self.assertContains(response, 'privacy@example.com')
        self.assertContains(response, 'within 30 days')


class HealthCheckTests(TestCase):
    """Tests runtime health reporting.

    Args:
        None.

    Returns:
        None.
    """

    def test_healthz_reports_database_ready(self):
        """Expose a non-cacheable health endpoint for container checks.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get('/healthz/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})
        self.assertEqual(response['Cache-Control'], 'no-store')


class DashboardTests(TestCase):
    """Tests commissioner dashboard workflows.

    Args:
        None.

    Returns:
        None.
    """

    def setUp(self):
        """Create a staff user for dashboard tests.

        Args:
            None.

        Returns:
            None.
        """
        self.staff_user = User.objects.create_user(
            username='dashboard_staff',
            email='dashboard@example.com',
            password='password',
            is_staff=True,
        )

    def login_staff(self):
        """Authenticate the test client as the dashboard staff user.

        Args:
            None.

        Returns:
            bool: True when login succeeds.
        """
        return self.client.login(username='dashboard_staff', password='password')

    def test_dashboard_requires_staff(self):
        """Require staff authentication before showing the dashboard.

        Args:
            None.

        Returns:
            None.
        """
        response = self.client.get(reverse('boards:dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_can_create_board_from_dashboard(self):
        """Create a board through the dashboard form.

        Args:
            None.

        Returns:
            None.
        """
        game = make_game()
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard'),
            data={
                'game': game.pk,
                'name': 'Dashboard Created Board',
                'entry_fee': '15.00',
                'notes': 'Dashboard test notes',
                'payout_q1_pct': 25,
                'payout_q2_pct': 25,
                'payout_q3_pct': 25,
                'payout_q4_pct': 25,
            },
        )
        board = Board.objects.get(name='Dashboard Created Board')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(board.created_by, self.staff_user)
        self.assertEqual(response.url, reverse('boards:dashboard_detail', args=[board.access_token]))

    def test_dashboard_can_assign_numbers(self):
        """Lock a board and assign numbers from the dashboard.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Lock From Dashboard', created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'assign_numbers'},
        )
        board.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(board.is_locked)
        self.assertEqual(sorted(board.home_numbers), list(range(10)))
        self.assertEqual(sorted(board.away_numbers), list(range(10)))

    def test_dashboard_assign_numbers_has_confirmation_guard(self):
        """Warn commissioners before locking a board and assigning digits.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Confirm Lock', created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.get(reverse('boards:dashboard_detail', args=[board.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Assign numbers and lock this board?')

    def test_dashboard_can_mark_square_paid_and_unpaid(self):
        """Toggle payment state from the dashboard.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Payment Dashboard', created_by=self.staff_user,
        )
        square = Square.objects.create(board=board, row=0, col=0, name='Pay Me')
        self.login_staff()

        paid_response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'mark_paid', 'square_id': square.pk},
        )
        square.refresh_from_db()
        self.assertEqual(paid_response.status_code, 302)
        self.assertTrue(square.paid)
        self.assertEqual(square.paid_by, self.staff_user)

        unpaid_response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'mark_unpaid', 'square_id': square.pk},
        )
        square.refresh_from_db()
        self.assertEqual(unpaid_response.status_code, 302)
        self.assertFalse(square.paid)
        self.assertIsNone(square.paid_by)

    def test_dashboard_can_regenerate_public_link(self):
        """Rotate the board token from the staff dashboard.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(),
            name='Rotate Link Dashboard',
            access_token='legacy2',
            created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'regenerate_token'},
        )
        board.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(board.access_token, 'legacy2')
        self.assertGreaterEqual(len(board.access_token), 20)
        self.assertEqual(response.url, reverse('boards:dashboard_detail', args=[board.access_token]))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_dashboard_can_send_invite(self):
        """Send a participant invite from the dashboard.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Invite Dashboard', entry_fee=10,
            created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'send_invite', 'to_email': 'player@example.com'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(board.access_token, mail.outbox[0].body)

    @override_settings(ALLOWED_HOSTS=['pool.trycloudflare.com', 'testserver'])
    def test_dashboard_public_link_uses_current_request_host(self):
        """Build share links from the public request host when available.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Tunnel Share Link', created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.get(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            HTTP_HOST='pool.trycloudflare.com',
            HTTP_X_FORWARDED_PROTO='https',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'https://pool.trycloudflare.com{board.get_absolute_url()}')

    def test_staff_cannot_manage_another_commissioners_board(self):
        """Hide commissioner dashboards from unrelated staff accounts.

        Args:
            None.

        Returns:
            None.
        """
        other_staff = User.objects.create_user(
            username='other_staff',
            email='other@example.com',
            password='password',
            is_staff=True,
        )
        board = Board.objects.create(
            game=make_game(), name='Other Board', created_by=other_staff,
        )
        self.login_staff()

        response = self.client.get(reverse('boards:dashboard_detail', args=[board.access_token]))

        self.assertEqual(response.status_code, 404)

    def test_dashboard_can_release_a_claim(self):
        """Clear participant and payment details from a released square.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Release Claim', created_by=self.staff_user,
        )
        square = Square.objects.create(
            board=board,
            row=0,
            col=0,
            name='Release Me',
            email='release@example.com',
            claimed_at=timezone.now(),
            paid=True,
            paid_at=timezone.now(),
            paid_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'release_claim', 'square_id': square.pk},
        )
        square.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(square.name, '')
        self.assertEqual(square.email, '')
        self.assertIsNone(square.claimed_at)
        self.assertFalse(square.paid)
        self.assertIsNone(square.paid_by)

    @patch('boards.views.send_mail', side_effect=RuntimeError('SMTP unavailable'))
    def test_dashboard_reports_invite_delivery_failure(self, mocked_send_mail):
        """Show commissioners a useful error when an invite cannot be sent.

        Args:
            mocked_send_mail (Mock): Patched mail sender used to simulate failure.

        Returns:
            None.
        """
        board = Board.objects.create(
            game=make_game(), name='Failed Invite', created_by=self.staff_user,
        )
        self.login_staff()

        response = self.client.post(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            data={'action': 'send_invite', 'to_email': 'player@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The invite could not be sent')
        mocked_send_mail.assert_called_once()
