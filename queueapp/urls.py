from django.urls import path

from . import views

urlpatterns = [
    path('status/', views.queue_status, name='queue-status'),
    path('book/', views.book_token, name='book-token'),
    path('next/', views.call_next, name='call-next'),
    path('cancel/<int:token_number>/', views.cancel_token, name='cancel-token'),
    path('reset/', views.reset_queue, name='reset-queue'),
]
