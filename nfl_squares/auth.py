from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect


def _normalise_values(values):
    """Convert comma-separated settings into lowercase values.

    Args:
        values (str | list[str] | tuple[str, ...]): Raw setting value from the environment.

    Returns:
        set[str]: Normalized, non-empty values.
    """
    if isinstance(values, str):
        raw_values = values.split(',')
    else:
        raw_values = values
    return {value.strip().lower() for value in raw_values if value and value.strip()}


def _social_email(sociallogin):
    """Read the verified email address from an allauth social login.

    Args:
        sociallogin (allauth.socialaccount.models.SocialLogin): Login state from the OAuth provider.

    Returns:
        str: Lowercase email address, or an empty string when none is provided.
    """
    user_email = getattr(sociallogin.user, 'email', '') or ''
    account = getattr(sociallogin, 'account', None)
    provider_email = ''
    if account:
        provider_email = account.extra_data.get('email', '') or ''
    return (user_email or provider_email).strip().lower()


def _email_domain(email):
    """Extract the domain portion of an email address.

    Args:
        email (str): Email address to inspect.

    Returns:
        str: Lowercase domain, or an empty string when the address is malformed.
    """
    if '@' not in email:
        return ''
    return email.rsplit('@', 1)[1].lower()


def _has_existing_staff_user(email):
    """Check whether an email belongs to an active staff user.

    Args:
        email (str): Email address to check.

    Returns:
        bool: True when an active staff account already uses the email.
    """
    User = get_user_model()
    return User.objects.filter(email__iexact=email, is_active=True, is_staff=True).exists()


def _is_configured_staff_email(email):
    """Check whether OAuth settings allow staff access for an email.

    Args:
        email (str): Email address to check.

    Returns:
        bool: True when email or domain allowlist settings permit staff access.
    """
    staff_emails = _normalise_values(settings.ADMIN_OAUTH_STAFF_EMAILS)
    staff_domains = _normalise_values(settings.ADMIN_OAUTH_STAFF_DOMAINS)
    superuser_emails = _normalise_values(settings.ADMIN_OAUTH_SUPERUSER_EMAILS)
    return (
        email in staff_emails
        or email in superuser_emails
        or _email_domain(email) in staff_domains
    )


def _is_configured_superuser_email(email):
    """Check whether OAuth settings allow superuser access for an email.

    Args:
        email (str): Email address to check.

    Returns:
        bool: True when the explicit superuser email allowlist contains the email.
    """
    return email in _normalise_values(settings.ADMIN_OAUTH_SUPERUSER_EMAILS)


def _is_allowed_admin_email(email):
    """Check whether an OAuth email is allowed to enter the admin area.

    Args:
        email (str): Email address returned by the OAuth provider.

    Returns:
        bool: True when the email maps to an existing staff account or configured allowlist.
    """
    if not email:
        return False
    return _has_existing_staff_user(email) or _is_configured_staff_email(email)


class AdminSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Restrict social login to configured admin identities.

    Args:
        request (HttpRequest | None): Optional request passed by django-allauth.

    Returns:
        None.
    """

    def pre_social_login(self, request, sociallogin):
        """Abort OAuth login before session creation when the email is not allowed.

        Args:
            request (HttpRequest): Current HTTP request.
            sociallogin (allauth.socialaccount.models.SocialLogin): OAuth login state.

        Returns:
            None.

        Raises:
            ImmediateHttpResponse: If the OAuth email is missing or not authorized.
        """
        email = _social_email(sociallogin)
        if not _is_allowed_admin_email(email):
            messages.error(
                request,
                'That Google account is not allowed to access this admin panel.',
            )
            raise ImmediateHttpResponse(redirect('admin:login'))

    def is_open_for_signup(self, request, sociallogin):
        """Allow OAuth-created users only when explicitly configured for admin access.

        Args:
            request (HttpRequest): Current HTTP request.
            sociallogin (allauth.socialaccount.models.SocialLogin): OAuth login state.

        Returns:
            bool: True when a new OAuth user may be created.
        """
        return _is_configured_staff_email(_social_email(sociallogin))

    def save_user(self, request, sociallogin, form=None):
        """Persist a new OAuth user and apply configured admin flags.

        Args:
            request (HttpRequest): Current HTTP request.
            sociallogin (allauth.socialaccount.models.SocialLogin): OAuth login state.
            form (Form | None): Optional allauth signup form.

        Returns:
            User: Saved Django user instance.
        """
        user = super().save_user(request, sociallogin, form)
        email = (user.email or '').lower()
        update_fields = []

        if _is_configured_staff_email(email) and not user.is_staff:
            user.is_staff = True
            update_fields.append('is_staff')

        if _is_configured_superuser_email(email) and not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            update_fields.extend(['is_superuser', 'is_staff'])

        if update_fields:
            user.save(update_fields=sorted(set(update_fields)))
        return user
