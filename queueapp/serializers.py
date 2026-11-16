from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Token


class StaffUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'is_staff',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


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
