from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone

from .forms import ClaimSquaresForm
from .models import Board, Square


def board_list(request):
    boards = Board.objects.select_related('game').order_by('-created_at')
    return render(request, 'boards/board_list.html', {'boards': boards})


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

            # Verify squares are still available
            claimed = []
            already_taken = []
            for row, col in pairs:
                square, created = Square.objects.get_or_create(
                    board=board, row=row, col=col,
                )
                if not created and square.is_claimed:
                    already_taken.append(f"({row},{col})")
                else:
                    square.name = name
                    square.email = email
                    square.claimed_at = timezone.now()
                    square.save(update_fields=['name', 'email', 'claimed_at'])
                    claimed.append(square)

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
