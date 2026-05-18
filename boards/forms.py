from django import forms

from games.models import NFLGame

from .models import Board


FIELD_CLASS = 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500'


class ClaimSquaresForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Your Name',
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Full name',
            'autofocus': True,
        }),
    )
    email = forms.EmailField(
        required=False,
        label='Email (optional)',
        widget=forms.EmailInput(attrs={
            'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'you@example.com',
        }),
    )
    squares = forms.CharField(
        widget=forms.HiddenInput(),
        help_text='Comma-separated list of row,col pairs e.g. "0,3;2,7"',
    )

    def clean_squares(self):
        """Parse selected board coordinates from the hidden form field.

        Args:
            None.

        Returns:
            list[tuple[int, int]]: Unique row and column coordinates selected by the claimant.

        Raises:
            forms.ValidationError: If no squares are selected or a coordinate is invalid.
        """
        raw = self.cleaned_data['squares'].strip()
        if not raw:
            raise forms.ValidationError('Please select at least one square.')
        pairs = []
        seen = set()
        for part in raw.split(';'):
            part = part.strip()
            if not part:
                continue
            try:
                r, c = part.split(',')
                r, c = int(r), int(c)
                if not (0 <= r <= 9 and 0 <= c <= 9):
                    raise ValueError
                if (r, c) not in seen:
                    seen.add((r, c))
                    pairs.append((r, c))
            except (ValueError, AttributeError):
                raise forms.ValidationError(f'Invalid square: "{part}"')
        if not pairs:
            raise forms.ValidationError('Please select at least one square.')
        return pairs


class DashboardBoardForm(forms.ModelForm):
    """Create commissioner-managed boards from the dashboard.

    Args:
        *args (Any): Positional arguments forwarded to forms.ModelForm.
        **kwargs (Any): Keyword arguments forwarded to forms.ModelForm.

    Returns:
        None.
    """

    game = forms.ModelChoiceField(
        queryset=NFLGame.objects.none(),
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )

    class Meta:
        """Model binding for dashboard board creation.

        Args:
            None.

        Returns:
            None.
        """

        model = Board
        fields = [
            'game',
            'name',
            'entry_fee',
            'notes',
            'payout_q1_pct',
            'payout_q2_pct',
            'payout_q3_pct',
            'payout_q4_pct',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': FIELD_CLASS,
                'placeholder': 'Sunday Night Board',
            }),
            'entry_fee': forms.NumberInput(attrs={
                'class': FIELD_CLASS,
                'min': '0',
                'step': '0.01',
            }),
            'notes': forms.Textarea(attrs={
                'class': FIELD_CLASS,
                'rows': 3,
                'placeholder': 'Payment instructions shown on the public board.',
            }),
            'payout_q1_pct': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'max': '100'}),
            'payout_q2_pct': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'max': '100'}),
            'payout_q3_pct': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'max': '100'}),
            'payout_q4_pct': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the dashboard board form with game choices.

        Args:
            *args (Any): Positional arguments forwarded to forms.ModelForm.
            **kwargs (Any): Keyword arguments forwarded to forms.ModelForm.

        Returns:
            None.
        """
        super().__init__(*args, **kwargs)
        self.fields['game'].queryset = NFLGame.objects.order_by('-season', 'week', 'game_date')


class InviteParticipantForm(forms.Form):
    """Collect a participant email for dashboard invites.

    Args:
        *args (Any): Positional arguments forwarded to forms.Form.
        **kwargs (Any): Keyword arguments forwarded to forms.Form.

    Returns:
        None.
    """

    to_email = forms.EmailField(
        label='Participant email',
        widget=forms.EmailInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'player@example.com',
        }),
    )
