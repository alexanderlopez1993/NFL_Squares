from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from games.models import NFLGame

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
        board = Board.objects.create(game=make_game(), name='Lock From Dashboard')
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

    def test_dashboard_can_mark_square_paid_and_unpaid(self):
        """Toggle payment state from the dashboard.

        Args:
            None.

        Returns:
            None.
        """
        board = Board.objects.create(game=make_game(), name='Payment Dashboard')
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
        board = Board.objects.create(game=make_game(), name='Invite Dashboard', entry_fee=10)
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
        board = Board.objects.create(game=make_game(), name='Tunnel Share Link')
        self.login_staff()

        response = self.client.get(
            reverse('boards:dashboard_detail', args=[board.access_token]),
            HTTP_HOST='pool.trycloudflare.com',
            HTTP_X_FORWARDED_PROTO='https',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'https://pool.trycloudflare.com{board.get_absolute_url()}')
