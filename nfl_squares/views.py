from allauth.socialaccount.providers.google.views import oauth2_login
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


def google_oauth_login(request):
    """Start Google OAuth only after credentials are configured.

    Args:
        request (HttpRequest): Current request.

    Returns:
        HttpResponse: Google OAuth response or redirect to the admin login page.
    """
    if not settings.GOOGLE_OAUTH_CONFIGURED:
        messages.error(
            request,
            'Google OAuth is not configured yet. Set GOOGLE_OAUTH_CLIENT_ID and '
            'GOOGLE_OAUTH_CLIENT_SECRET to enable it.',
        )
        return redirect('admin:login')
    return oauth2_login(request)
