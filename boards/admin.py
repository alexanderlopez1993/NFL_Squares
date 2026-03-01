from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
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
