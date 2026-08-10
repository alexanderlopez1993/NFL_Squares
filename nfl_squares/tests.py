from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .auth import (
    _is_allowed_admin_email,
    _is_configured_staff_email,
    _is_configured_superuser_email,
)


class AdminOAuthPolicyTests(TestCase):
    """Tests commissioner allowlist and privilege policy helpers.

    Args:
        None.

    Returns:
        None.
    """

    @override_settings(
        ADMIN_OAUTH_STAFF_EMAILS=['commissioner@example.com'],
        ADMIN_OAUTH_STAFF_DOMAINS=[],
        ADMIN_OAUTH_SUPERUSER_EMAILS=[],
    )
    def test_explicit_staff_email_is_allowed(self):
        """Allow an exact email configured for commissioner access.

        Args:
            None.

        Returns:
            None.
        """
        self.assertTrue(_is_configured_staff_email('commissioner@example.com'))
        self.assertFalse(_is_configured_staff_email('other@example.com'))

    @override_settings(
        ADMIN_OAUTH_STAFF_EMAILS=[],
        ADMIN_OAUTH_STAFF_DOMAINS=['example.com'],
        ADMIN_OAUTH_SUPERUSER_EMAILS=[],
    )
    def test_staff_domain_requires_an_exact_domain(self):
        """Reject lookalike and subdomain addresses outside the exact allowlist.

        Args:
            None.

        Returns:
            None.
        """
        self.assertTrue(_is_configured_staff_email('commissioner@example.com'))
        self.assertFalse(_is_configured_staff_email('commissioner@fakeexample.com'))
        self.assertFalse(_is_configured_staff_email('commissioner@sub.example.com'))

    @override_settings(
        ADMIN_OAUTH_STAFF_EMAILS=[],
        ADMIN_OAUTH_STAFF_DOMAINS=[],
        ADMIN_OAUTH_SUPERUSER_EMAILS=[],
    )
    def test_existing_active_staff_email_is_allowed(self):
        """Permit OAuth login for an existing active staff account.

        Args:
            None.

        Returns:
            None.
        """
        User = get_user_model()
        User.objects.create_user(
            username='existing_staff',
            email='existing@example.com',
            password='password',
            is_staff=True,
        )

        self.assertTrue(_is_allowed_admin_email('existing@example.com'))
        self.assertFalse(_is_allowed_admin_email('unknown@example.com'))

    @override_settings(ADMIN_OAUTH_SUPERUSER_EMAILS=['owner@example.com'])
    def test_superuser_requires_explicit_email_allowlist(self):
        """Grant superuser eligibility only to an exact configured email.

        Args:
            None.

        Returns:
            None.
        """
        self.assertTrue(_is_configured_superuser_email('owner@example.com'))
        self.assertFalse(_is_configured_superuser_email('commissioner@example.com'))
