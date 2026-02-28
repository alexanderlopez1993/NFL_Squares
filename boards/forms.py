from django import forms


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
        raw = self.cleaned_data['squares'].strip()
        if not raw:
            raise forms.ValidationError('Please select at least one square.')
        pairs = []
        for part in raw.split(';'):
            part = part.strip()
            if not part:
                continue
            try:
                r, c = part.split(',')
                r, c = int(r), int(c)
                if not (0 <= r <= 9 and 0 <= c <= 9):
                    raise ValueError
                pairs.append((r, c))
            except (ValueError, AttributeError):
                raise forms.ValidationError(f'Invalid square: "{part}"')
        if not pairs:
            raise forms.ValidationError('Please select at least one square.')
        return pairs
