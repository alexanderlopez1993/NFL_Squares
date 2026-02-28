from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('boards/', include('boards.urls', namespace='boards')),
    path('', RedirectView.as_view(pattern_name='boards:list', permanent=False)),
]
