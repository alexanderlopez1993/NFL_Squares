from django.urls import path
from . import views

app_name = 'boards'

urlpatterns = [
    path('', views.board_list, name='list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<str:token>/', views.dashboard_board, name='dashboard_detail'),
    path('<str:token>/', views.board_detail, name='detail'),
    path('<str:token>/claim/', views.claim_squares, name='claim'),
    path('<str:token>/scores/', views.game_score_partial, name='scores_partial'),
]
