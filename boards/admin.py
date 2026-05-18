from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Board, Square


class SquareInline(admin.TabularInline):
    model = Square
    extra = 0
    fields = ['row', 'col', 'name', 'email', 'paid', 'claimed_at']
    readonly_fields = ['row', 'col', 'claimed_at']
    ordering = ['row', 'col']
    can_delete = False
    max_num = 100


def assign_numbers_action(modeladmin, request, queryset):
    count = 0
    for board in queryset:
        if not board.is_locked:
            board.assign_numbers()
            count += 1
    messages.success(request, f'Assigned numbers to {count} board(s).')


assign_numbers_action.short_description = 'Assign numbers and lock selected boards'


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'game', 'entry_fee', 'claimed_count', 'paid_count',
        'total_pot', 'is_locked', 'created_at', 'board_link',
    ]
    list_filter = ['is_locked', 'game__season']
    search_fields = ['name', 'game__home_team', 'game__away_team']
    readonly_fields = ['access_token', 'created_at', 'numbers_assigned_at', 'board_link']
    actions = [assign_numbers_action]
    inlines = [SquareInline]

    fieldsets = [
        ('Board Info', {
            'fields': ['name', 'game', 'notes', 'entry_fee', 'created_by'],
        }),
        ('Payouts (must sum to 100)', {
            'fields': ['payout_q1_pct', 'payout_q2_pct', 'payout_q3_pct', 'payout_q4_pct'],
        }),
        ('Access & State', {
            'fields': ['access_token', 'board_link', 'is_locked', 'numbers_assigned_at',
                       'home_numbers', 'away_numbers', 'created_at'],
        }),
    ]

    def get_urls(self):
        """Register board-specific admin actions.

        Args:
            None.

        Returns:
            list[URLPattern]: Custom board URLs followed by default admin URLs.
        """
        custom_urls = [
            path(
                '<int:board_id>/send-invite/',
                self.admin_site.admin_view(self.send_invite_view),
                name='boards_board_send_invite',
            ),
        ]
        return custom_urls + super().get_urls()

    def send_invite_view(self, request, board_id):
        """Send a participant invite email from the board admin page.

        Args:
            request (HttpRequest): Current admin request.
            board_id (int): Primary key of the board being shared.

        Returns:
            HttpResponse: Invite form response or redirect back to the board.
        """
        board = get_object_or_404(Board.objects.select_related('game'), pk=board_id)
        board_url = request.build_absolute_uri(board.get_absolute_url())
        change_url = reverse('admin:boards_board_change', args=[board_id])

        if request.method == 'POST':
            to_email = request.POST.get('to_email', '').strip()
            if not to_email:
                messages.error(request, 'Please enter a valid email address.')
            else:
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
                return redirect(change_url)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Send Invite - {board.name}',
            'board': board,
            'board_url': board_url,
            'cancel_url': change_url,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/boards/board/send_invite.html', context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Add a send-invite object tool to existing board admin pages.

        Args:
            request (HttpRequest): Current admin request.
            object_id (str): Primary key of the board being edited.
            form_url (str): Optional form URL supplied by Django admin.
            extra_context (dict | None): Additional template context.

        Returns:
            HttpResponse: Default board change response with extra context.
        """
        extra_context = extra_context or {}
        if object_id:
            extra_context['send_invite_url'] = reverse(
                'admin:boards_board_send_invite',
                args=[object_id],
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def board_link(self, obj):
        if obj.pk:
            url = obj.get_absolute_url()
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return '—'
    board_link.short_description = 'Public Link'


def mark_paid_action(modeladmin, request, queryset):
    for square in queryset:
        square.mark_paid(admin_user=request.user)
    messages.success(request, f'Marked {queryset.count()} square(s) as paid.')


mark_paid_action.short_description = 'Mark selected squares as paid'


def mark_unpaid_action(modeladmin, request, queryset):
    queryset.update(paid=False, paid_at=None, paid_by=None)
    messages.success(request, f'Marked {queryset.count()} square(s) as unpaid.')


mark_unpaid_action.short_description = 'Mark selected squares as unpaid'


@admin.register(Square)
class SquareAdmin(admin.ModelAdmin):
    list_display = ['board', 'row', 'col', 'name', 'email', 'paid', 'claimed_at', 'paid_at']
    list_filter = ['paid', 'board__game', 'board']
    search_fields = ['name', 'email', 'board__name']
    readonly_fields = ['claimed_at', 'paid_at', 'paid_by']
    actions = [mark_paid_action, mark_unpaid_action]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('board', 'board__game')
