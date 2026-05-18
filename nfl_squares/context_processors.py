from django.conf import settings


def oauth_status(request):
    """Expose OAuth setup status to templates.

    Args:
        request (HttpRequest): Current request.

    Returns:
        dict[str, bool]: Template context flags for OAuth availability.
    """
    return {
        'google_oauth_configured': settings.GOOGLE_OAUTH_CONFIGURED,
    }
