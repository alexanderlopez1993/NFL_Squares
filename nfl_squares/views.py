from allauth.socialaccount.providers.google.views import oauth2_login
from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render


def healthz(request):
    """Return application health after checking database connectivity.

    Args:
        request (HttpRequest): Current request.

    Returns:
        JsonResponse: Health payload with a 200 status when the database is
        reachable, or a 503 status when the database check fails.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        response = JsonResponse(
            {'status': 'unhealthy', 'database': 'unavailable'},
            status=503,
        )
        response['Cache-Control'] = 'no-store'
        return response

    response = JsonResponse({'status': 'ok', 'database': 'ok'})
    response['Cache-Control'] = 'no-store'
    return response


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


def privacy_notice(request):
    """Explain participant data handling for private board links.

    Args:
        request (HttpRequest): Current request.

    Returns:
        HttpResponse: Public privacy notice with configured contact details.
    """
    return render(request, 'privacy.html', {
        'contact_email': settings.PRIVACY_CONTACT_EMAIL,
        'retention_days': settings.DATA_RETENTION_DAYS,
    })
