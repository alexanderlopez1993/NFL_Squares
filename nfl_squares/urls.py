from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from .views import google_oauth_login, healthz, privacy_notice

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('privacy/', privacy_notice, name='privacy'),
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=True)),
    path('accounts/google/login/', google_oauth_login, name='google_login'),
    path('accounts/', include('allauth.urls')),
    path('boards/', include('boards.urls', namespace='boards')),
    path('', RedirectView.as_view(pattern_name='boards:dashboard', permanent=False)),
]
