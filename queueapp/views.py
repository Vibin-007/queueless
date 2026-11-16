from django.contrib.auth import authenticate
from collections import Counter
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Token
from .permissions import IsStaffUser
from .serializers import StaffUserSerializer, TokenSerializer

SERVICE_TYPES = {choice[0] for choice in Token.SERVICE_CHOICES}
ESTIMATED_MINUTES_PER_TOKEN = 5
FIRST_TOKEN_NUMBER = 101


def _queue_payload():
    serving = (
        Token.objects.filter(status=Token.STATUS_SERVING)
        .order_by('created_at', 'id')
        .first()
    )
    waiting = Token.objects.filter(status=Token.STATUS_WAITING).order_by(
        'created_at', 'id'
    )
    total_waiting = waiting.count()
    return {
        'now_serving': TokenSerializer(serving).data if serving else None,
        'waiting_list': TokenSerializer(waiting, many=True).data,
        'total_waiting': total_waiting,
        'est_wait_minutes': total_waiting * ESTIMATED_MINUTES_PER_TOKEN,
    }


@api_view(['POST'])
def staff_login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not isinstance(username, str) or not isinstance(password, str):
        return Response(
            {'error': 'username and password are required.'},
            status=400,
        )
    username = username.strip()
    if not username or not password:
        return Response(
            {'error': 'username and password are required.'},
            status=400,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {'error': 'Invalid username or password.'},
            status=400,
        )
    if not user.is_staff:
        return Response(
            {'error': 'This account does not have staff access.'},
            status=403,
        )

    token, _ = AuthToken.objects.get_or_create(user=user)
    return Response(
        {
            'token': token.key,
            'user': StaffUserSerializer(user).data,
        }
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def staff_logout(request):
    if isinstance(request.auth, AuthToken):
        request.auth.delete()
    return Response(status=204)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsStaffUser])
def staff_me(request):
    return Response(StaffUserSerializer(request.user).data)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsStaffUser])
def queue_analytics(request):
    today = timezone.localdate()
    first_day = today - timedelta(days=6)
    window_start = timezone.make_aware(
        datetime.combine(first_day, time.min)
    )
    tokens = list(
        Token.objects.filter(created_at__gte=window_start).only(
            'created_at', 'started_at', 'completed_at', 'status'
        )
    )

    daily_counts = Counter(timezone.localtime(token.created_at).date() for token in tokens)
    hourly_counts = Counter(timezone.localtime(token.created_at).hour for token in tokens)
    wait_minutes = [
        (token.started_at - token.created_at).total_seconds() / 60
        for token in tokens
        if token.started_at
    ]
    service_minutes = [
        (token.completed_at - token.started_at).total_seconds() / 60
        for token in tokens
        if token.started_at and token.completed_at
    ]
    eligible = [token for token in tokens if token.status != Token.STATUS_CANCELLED]
    completed = sum(token.status == Token.STATUS_COMPLETED for token in eligible)
    completion_rate = round(completed / len(eligible) * 100) if eligible else 0

    return Response(
        {
            'period_days': 7,
            'daily_customers': [
                {
                    'date': (first_day + timedelta(days=offset)).isoformat(),
                    'customers': daily_counts.get(
                        first_day + timedelta(days=offset), 0
                    ),
                }
                for offset in range(7)
            ],
            'peak_hour': (
                max(hourly_counts, key=hourly_counts.get)
                if hourly_counts
                else None
            ),
            'peak_hour_customers': max(hourly_counts.values(), default=0),
            'average_wait_minutes': (
                round(sum(wait_minutes) / len(wait_minutes), 1)
                if wait_minutes
                else None
            ),
            'average_service_minutes': (
                round(sum(service_minutes) / len(service_minutes), 1)
                if service_minutes
                else None
            ),
            'completed_customers': completed,
            'completion_rate': completion_rate,
        }
    )


@api_view(['GET'])
def queue_status(request):
    return Response(_queue_payload())


@api_view(['POST'])
def book_token(request):
    customer_name = (request.data.get('customer_name') or '').strip()
    service_type = request.data.get('service_type') or Token.SERVICE_GENERAL

    if not customer_name:
        return Response(
            {'error': 'customer_name is required.'},
            status=400,
        )
    if len(customer_name) > 100:
        return Response(
            {'error': 'customer_name must be 100 characters or fewer.'},
            status=400,
        )
    if service_type not in SERVICE_TYPES:
        return Response(
            {'error': f'service_type must be one of {sorted(SERVICE_TYPES)}.'},
            status=400,
        )

    with transaction.atomic():
        last_token = (
            Token.objects.select_for_update()
            .order_by('-token_number')
            .first()
        )
        next_number = (
            last_token.token_number + 1
            if last_token
            else FIRST_TOKEN_NUMBER
        )
        token = Token.objects.create(
            token_number=next_number,
            customer_name=customer_name,
            service_type=service_type,
            status=Token.STATUS_WAITING,
        )

    return Response(TokenSerializer(token).data, status=201)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsStaffUser])
def call_next(request):
    now = timezone.now()
    with transaction.atomic():
        Token.objects.filter(status=Token.STATUS_SERVING).update(
            status=Token.STATUS_COMPLETED,
            completed_at=now,
        )
        next_token = (
            Token.objects.select_for_update()
            .filter(status=Token.STATUS_WAITING)
            .order_by('created_at', 'id')
            .first()
        )
        if next_token:
            next_token.status = Token.STATUS_SERVING
            next_token.started_at = now
            next_token.save(update_fields=['status', 'started_at'])

    payload = _queue_payload()
    payload['called'] = TokenSerializer(next_token).data if next_token else None
    return Response(payload)


def _cancel_waiting_token(token_number):
    token = (
        Token.objects.filter(
            token_number=token_number,
            status=Token.STATUS_WAITING,
        )
        .order_by('created_at', 'id')
        .first()
    )
    if token is None:
        return Response(
            {'error': f'No waiting token found with number {token_number}.'},
            status=404,
        )

    token.status = Token.STATUS_CANCELLED
    token.save(update_fields=['status'])
    return Response(
        {
            'message': f'Token #{token.token_number} has left the queue.',
            'token': TokenSerializer(token).data,
            **_queue_payload(),
        }
    )


@api_view(['POST'])
def cancel_token(request, token_number):
    return _cancel_waiting_token(token_number)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsStaffUser])
def skip_token(request, token_number):
    return _cancel_waiting_token(token_number)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsStaffUser])
def reset_queue(request):
    deleted_count, _ = Token.objects.all().delete()
    return Response(
        {
            'message': 'Queue reset successfully.',
            'deleted': deleted_count,
            **_queue_payload(),
        }
    )
