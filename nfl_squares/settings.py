import os
from pathlib import Path

import dj_database_url
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = config('APP_ENV', default='dev')
if APP_ENV not in {'dev', 'prod'}:
    raise RuntimeError('APP_ENV must be either "dev" or "prod".')

DEBUG = config('DEBUG', default=True, cast=bool)
if APP_ENV == 'prod' and DEBUG:
    raise RuntimeError('DEBUG must be False when APP_ENV=prod.')
_DEFAULT_DEV_SECRET_KEY = 'dev-insecure-key-change-in-production'
_PLACEHOLDER_SECRET_KEYS = {_DEFAULT_DEV_SECRET_KEY, 'change-me-to-a-long-random-string'}
SECRET_KEY = config('SECRET_KEY', default=_DEFAULT_DEV_SECRET_KEY if DEBUG else '')
if not DEBUG and (
    not SECRET_KEY
    or SECRET_KEY in _PLACEHOLDER_SECRET_KEYS
    or len(SECRET_KEY) < 32
):
    raise RuntimeError('SECRET_KEY must be a strong unique value of at least 32 characters when DEBUG=False.')

_RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
_DEFAULT_ALLOWED_HOSTS = (
    _RENDER_EXTERNAL_HOSTNAME
    if _RENDER_EXTERNAL_HOSTNAME
    else 'localhost,127.0.0.1,.trycloudflare.com'
)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default=_DEFAULT_ALLOWED_HOSTS, cast=Csv())
_DEFAULT_CSRF_ORIGINS = (
    f'https://{_RENDER_EXTERNAL_HOSTNAME}' if _RENDER_EXTERNAL_HOSTNAME else ''
)
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default=_DEFAULT_CSRF_ORIGINS, cast=Csv())
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0 if DEBUG else 3600, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)
SECURE_REFERRER_POLICY = 'no-referrer'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'games.apps.GamesConfig',
    'boards.apps.BoardsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nfl_squares.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'nfl_squares.context_processors.oauth_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'nfl_squares.wsgi.application'

DB_CONN_MAX_AGE = config('DB_CONN_MAX_AGE', default=60, cast=int)
DATABASE_URL = config('DATABASE_URL', default='')

if config('USE_SQLITE', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
elif DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=DB_CONN_MAX_AGE,
            conn_health_checks=True,
            ssl_require=APP_ENV == 'prod',
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='nfl_squares'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'CONN_MAX_AGE': DB_CONN_MAX_AGE,
            'CONN_HEALTH_CHECKS': True,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/'

_DEFAULT_SITE_URL = (
    f'https://{_RENDER_EXTERNAL_HOSTNAME}'
    if _RENDER_EXTERNAL_HOSTNAME
    else 'http://localhost:8000'
)
SITE_URL = config('SITE_URL', default=_DEFAULT_SITE_URL).rstrip('/')

GOOGLE_OAUTH_CLIENT_ID = config('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = config('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_CONFIGURED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

SOCIALACCOUNT_ADAPTER = 'nfl_squares.auth.AdminSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
        'VERIFIED_EMAIL': True,
        'EMAIL_AUTHENTICATION': True,
        'EMAIL_AUTHENTICATION_AUTO_CONNECT': True,
    }
}

if GOOGLE_OAUTH_CONFIGURED:
    SOCIALACCOUNT_PROVIDERS['google']['APPS'] = [
        {
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'secret': GOOGLE_OAUTH_CLIENT_SECRET,
            'key': '',
        }
    ]

ADMIN_OAUTH_STAFF_EMAILS = config('ADMIN_OAUTH_STAFF_EMAILS', default='', cast=Csv())
ADMIN_OAUTH_STAFF_DOMAINS = config('ADMIN_OAUTH_STAFF_DOMAINS', default='', cast=Csv())
ADMIN_OAUTH_SUPERUSER_EMAILS = config('ADMIN_OAUTH_SUPERUSER_EMAILS', default='', cast=Csv())

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='NFL Squares <noreply@example.com>')
SERVER_EMAIL = config('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)
ADMIN_EMAILS = config('ADMIN_EMAILS', default='', cast=Csv())
ADMINS = [(email, email) for email in ADMIN_EMAILS]
PRIVACY_CONTACT_EMAIL = config('PRIVACY_CONTACT_EMAIL', default='')
DATA_RETENTION_DAYS = config('DATA_RETENTION_DAYS', default=30, cast=int)
if APP_ENV == 'prod' and EMAIL_BACKEND.endswith('console.EmailBackend'):
    raise RuntimeError('Configure a real email backend when APP_ENV=prod.')
if DATA_RETENTION_DAYS < 1:
    raise RuntimeError('DATA_RETENTION_DAYS must be at least 1.')

# ESPN API base URLs
ESPN_SCOREBOARD_URL = config(
    'ESPN_SCOREBOARD_URL',
    default='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard',
)
ESPN_REQUEST_TIMEOUT = config('ESPN_REQUEST_TIMEOUT', default=10, cast=int)

MAX_SQUARES_PER_PARTICIPANT = config('MAX_SQUARES_PER_PARTICIPANT', default=10, cast=int)
CLAIM_COOLDOWN_SECONDS = config('CLAIM_COOLDOWN_SECONDS', default=2, cast=int)
if not 1 <= MAX_SQUARES_PER_PARTICIPANT <= 100:
    raise RuntimeError('MAX_SQUARES_PER_PARTICIPANT must be between 1 and 100.')
if CLAIM_COOLDOWN_SECONDS < 0:
    raise RuntimeError('CLAIM_COOLDOWN_SECONDS cannot be negative.')

LOG_LEVEL = config('LOG_LEVEL', default='INFO')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django.request': {
            'handlers': ['console', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
