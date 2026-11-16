from django.contrib import admin

from .models import Token


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = (
        'token_number',
        'customer_name',
        'service_type',
        'status',
        'created_at',
    )
    list_filter = ('status', 'service_type')
    search_fields = ('customer_name',)
    ordering = ('created_at', 'id')
