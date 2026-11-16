from rest_framework import serializers

from .models import Token


class TokenSerializer(serializers.ModelSerializer):
    service_type_display = serializers.CharField(
        source='get_service_type_display',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )

    class Meta:
        model = Token
        fields = [
            'id',
            'token_number',
            'customer_name',
            'service_type',
            'service_type_display',
            'status',
            'status_display',
            'created_at',
        ]
        read_only_fields = fields
