import time

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.mail import send_mail
from django.db import OperationalError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ClaimSquaresForm, DashboardBoardForm, InviteParticipantForm
from .models import Board, Square

CLAIM_RETRY_ATTEMPTS = 3
CLAIM_RETRY_DELAY_SECONDS = 0.15


def _board_public_url(board, request=None):
    """Build an absolute public URL for a board.

    Args:
        board (Board): Board whose tokenized link should be shared.
        request (HttpRequest | None): Request used to derive the current public host.

    Returns:
        str: Absolute public URL for participants.
    """
    if request is not None:
        return request.build_absolute_uri(board.get_absolute_url())
    return f'{settings.SITE_URL}{board.get_absolute_url()}'


def _board_summary(board):
    """Build dashboard summary metrics for a board.

    Args:
        board (Board): Board to summarize.

    Returns:
        dict[str, Any]: Board, square counts, pot values, and claimed square rows.
    """
    squares = list(board.squares.all())
    claimed_squares = [square for square in squares if square.is_claimed]
    paid_squares = [square for square in claimed_squares if square.paid]
    return {
        'board': board,
        'claimed_count': len(claimed_squares),
        'paid_count': len(paid_squares),
        'unclaimed_count': 100 - len(claimed_squares),
        'unpaid_count': len(claimed_squares) - len(paid_squares),
        'total_pot': board.entry_fee * len(paid_squares),
        'claimed_squares': claimed_squares,
    }


@staff_member_required(login_url='admin:login')
def board_list(request):
    boards = Board.objects.select_related('game').order_by('-created_at')
    return render(request, 'boards/board_list.html', {'boards': boards})


@staff_member_required(login_url='admin:login')
def dashboard(request):
    """Render the commissioner dashboard and create new boards.

    Args:
        request (HttpRequest): Current request.

    Returns:
        HttpResponse: Dashboard page or redirect to a newly created board dashboard.
    """
    if request.method == 'POST':
        form = DashboardBoardForm(request.POST)
        if form.is_valid():
            board = form.save(commit=False)
            board.created_by = request.user
            board.save()
            messages.success(request, f'Created board "{board.name}".')
            return redirect('boards:dashboard_detail', token=board.access_token)
    else:
        form = DashboardBoardForm()

    boards = (
        Board.objects
        .select_related('game', 'created_by')
        .prefetch_related('squares')
        .order_by('-created_at')
    )
    summaries = [_board_summary(board) for board in boards]
    active_boards = [item for item in summaries if not item['board'].is_locked]
    locked_boards = [item for item in summaries if item['board'].is_locked]
    total_paid = sum(item['paid_count'] for item in summaries)
    total_claimed = sum(item['claimed_count'] for item in summaries)

    return render(request, 'boards/dashboard.html', {
        'form': form,
        'summaries': summaries,
        'active_boards': active_boards,
        'locked_boards': locked_boards,
        'total_boards': len(summaries),
        'total_claimed': total_claimed,
        'total_paid': total_paid,
    })


@staff_member_required(login_url='admin:login')
def dashboard_board(request, token):
    """Manage one board from the commissioner dashboard.

    Args:
        request (HttpRequest): Current request.
        token (str): Board access token.

    Returns:
        HttpResponse: Board dashboard page or redirect after a dashboard action.
    """
    board = get_object_or_404(
        Board.objects.select_related('game', 'created_by').prefetch_related('squares'),
        access_token=token,
    )
    invite_form = InviteParticipantForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_numbers':
            if board.is_locked:
                messages.warning(request, 'Numbers are already assigned for this board.')
            else:
                board.assign_numbers()
                messages.success(request, 'Numbers assigned and board locked.')
            return redirect('boards:dashboard_detail', token=token)

        if action == 'regenerate_token':
            board.regenerate_access_token()
            messages.success(request, 'Public board link regenerated.')
            return redirect('boards:dashboard_detail', token=board.access_token)

        if action in {'mark_paid', 'mark_unpaid'}:
            square = get_object_or_404(Square, pk=request.POST.get('square_id'), board=board)
            if action == 'mark_paid':
                square.mark_paid(admin_user=request.user)
                messages.success(request, f'Marked {square.name} as paid.')
            else:
                square.paid = False
                square.paid_at = None
                square.paid_by = None
                square.save(update_fields=['paid', 'paid_at', 'paid_by'])
                messages.success(request, f'Marked {square.name} as unpaid.')
            return redirect('boards:dashboard_detail', token=token)

        if action == 'send_invite':
            invite_form = InviteParticipantForm(request.POST)
            if invite_form.is_valid():
                to_email = invite_form.cleaned_data['to_email']
                board_url = _board_public_url(board, request)
                body = (
                    "You've been invited to join NFL Squares.\n\n"
                    f'Board: {board.name}\n'
                    f'Game: {board.game}\n'
                    f'Entry fee: ${board.entry_fee}\n\n'
                    'Open the link below to view the board and claim square(s):\n'
                    f'{board_url}\n'
                )
                if board.notes:
                    body += f'\nPayment info:\n{board.notes}\n'
                send_mail(
                    subject=f'Join NFL Squares: {board.name}',
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[to_email],
                )
                messages.success(request, f'Invite sent to {to_email}.')
                return redirect('boards:dashboard_detail', token=token)

    summary = _board_summary(board)
    public_url = _board_public_url(board, request)
    quarter_results = board.quarter_results() if board.is_locked else []

    return render(request, 'boards/dashboard_detail.html', {
        'board': board,
        'game': board.game,
        'summary': summary,
        'public_url': public_url,
        'invite_form': invite_form,
        'quarter_results': quarter_results,
    })


def board_detail(request, token):
    board = get_object_or_404(Board, access_token=token)
    game = board.game

    # Build a dict of squares keyed by (row, col) for fast lookup
    all_squares = list(board.squares.all())
    squares_by_pos = {(s.row, s.col): s for s in all_squares}

    # Compute winning cells for grid highlighting
    winning_cells = set()
    if board.is_locked and board.home_numbers:
        for q in range(1, 5):
            cell = board.winning_cell_for_quarter(q)
            if cell:
                winning_cells.add(cell)

    # Build grid with per-cell context
    grid = []
    for row in range(10):
        grid_row = []
        for col in range(10):
            square = squares_by_pos.get((row, col))
            home_digit = board.home_numbers[row] if board.is_locked and board.home_numbers else None
            away_digit = board.away_numbers[col] if board.is_locked and board.away_numbers else None
            grid_row.append({
                'square': square,
                'is_winner': (row, col) in winning_cells,
                'is_claimed': square and square.is_claimed,
                'is_paid': square and square.paid,
                'row': row,
                'col': col,
                'home_digit': home_digit,
                'away_digit': away_digit,
            })
        grid.append(grid_row)

    payout_schedule = [
        ('Q1', board.payout_q1_pct),
        ('Q2 / Halftime', board.payout_q2_pct),
        ('Q3', board.payout_q3_pct),
        ('Final', board.payout_q4_pct),
    ]

    context = {
        'board': board,
        'game': game,
        'grid': grid,
        'quarter_results': board.quarter_results() if board.is_locked else [],
        'unclaimed_count': 100 - len([s for s in all_squares if s.is_claimed]),
        'claimed_count': board.claimed_count,
        'paid_count': board.paid_count,
        'payout_schedule': payout_schedule,
    }
    return render(request, 'boards/board_detail.html', context)


def claim_squares(request, token):
    board = get_object_or_404(Board, access_token=token)

    if board.is_locked:
        messages.error(request, 'This board is locked — no new claims are accepted.')
        return redirect('boards:detail', token=token)

    if request.method == 'POST':
        form = ClaimSquaresForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            pairs = form.cleaned_data['squares']

            for attempt in range(CLAIM_RETRY_ATTEMPTS):
                try:
                    claimed = []
                    already_taken = []
                    with transaction.atomic():
                        locked_board = Board.objects.select_for_update().get(pk=board.pk)
                        if locked_board.is_locked:
                            messages.error(request, 'This board is locked — no new claims are accepted.')
                            return redirect('boards:detail', token=token)

                        # Lock each existing square before checking ownership so concurrent claims cannot overwrite it.
                        for row, col in pairs:
                            square, created = Square.objects.select_for_update().get_or_create(
                                board=locked_board, row=row, col=col,
                            )
                            if not created and square.is_claimed:
                                already_taken.append(f"({row},{col})")
                            else:
                                square.name = name
                                square.email = email
                                square.claimed_at = timezone.now()
                                square.save(update_fields=['name', 'email', 'claimed_at'])
                                claimed.append(square)
                    break
                except OperationalError:
                    if attempt == CLAIM_RETRY_ATTEMPTS - 1:
                        messages.error(
                            request,
                            'Another claim is being processed. Please try again in a moment.',
                        )
                        return redirect('boards:claim', token=token)
                    time.sleep(CLAIM_RETRY_DELAY_SECONDS)

            if already_taken:
                messages.warning(
                    request,
                    f"{len(already_taken)} square(s) were already taken and skipped: {', '.join(already_taken)}"
                )
            if claimed:
                messages.success(
                    request,
                    f"You claimed {len(claimed)} square(s)! "
                    f"{'Send payment to confirm your spot.' if board.entry_fee else ''}"
                )
                return redirect('boards:detail', token=token)
            else:
                messages.error(request, 'All selected squares were already taken. Please choose different ones.')
    else:
        # Pre-select a square if passed via query param
        preselect = request.GET.get('sq', '')  # e.g. "3,7"
        form = ClaimSquaresForm(initial={'squares': preselect})

    # Build available squares for the template grid
    existing = {(s.row, s.col): s for s in board.squares.all()}
    grid = []
    for row in range(10):
        grid_row = []
        for col in range(10):
            square = existing.get((row, col))
            grid_row.append({
                'row': row,
                'col': col,
                'row_label': row + 1,
                'col_label': chr(65 + col),
                'label': f'{chr(65 + col)}{row + 1}',
                'square': square,
                'is_available': not (square and square.is_claimed),
            })
        grid.append(grid_row)

    return render(request, 'boards/claim_form.html', {
        'board': board,
        'form': form,
        'grid': grid,
    })


def game_score_partial(request, token):
    """HTMX partial — returns just the score panel for live polling."""
    board = get_object_or_404(Board, access_token=token)
    return render(request, 'boards/partials/game_score.html', {
        'board': board,
        'game': board.game,
        'quarter_results': board.quarter_results() if board.is_locked else [],
    })
