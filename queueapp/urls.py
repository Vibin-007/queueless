from django.urls import path

from . import views

urlpatterns = [
    path('auth/login/', views.staff_login, name='staff-login'),
    path('auth/logout/', views.staff_logout, name='staff-logout'),
    path('auth/me/', views.staff_me, name='staff-me'),
    path('analytics/', views.queue_analytics, name='queue-analytics'),
    path('status/', views.queue_status, name='queue-status'),
    path('book/', views.book_token, name='book-token'),
    path('next/', views.call_next, name='call-next'),
    path('cancel/<int:token_number>/', views.cancel_token, name='cancel-token'),
    path('skip/<int:token_number>/', views.skip_token, name='skip-token'),
    path('reset/', views.reset_queue, name='reset-queue'),
]
