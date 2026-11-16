from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Token
from .serializers import TokenSerializer

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
def call_next(request):
    with transaction.atomic():
        Token.objects.filter(status=Token.STATUS_SERVING).update(
            status=Token.STATUS_COMPLETED
        )
        next_token = (
            Token.objects.select_for_update()
            .filter(status=Token.STATUS_WAITING)
            .order_by('created_at', 'id')
            .first()
        )
        if next_token:
            next_token.status = Token.STATUS_SERVING
            next_token.save(update_fields=['status'])

    payload = _queue_payload()
    payload['called'] = TokenSerializer(next_token).data if next_token else None
    return Response(payload)


@api_view(['POST'])
def cancel_token(request, token_number):
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
def reset_queue(request):
    deleted_count, _ = Token.objects.all().delete()
    return Response(
        {
            'message': 'Queue reset successfully.',
            'deleted': deleted_count,
            **_queue_payload(),
        }
    )
