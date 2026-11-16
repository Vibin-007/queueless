from django.db import models


class Token(models.Model):
    SERVICE_GENERAL = 'General'
    SERVICE_PRIORITY = 'Priority'
    SERVICE_SUPPORT = 'Support'
    SERVICE_CHOICES = [
        (SERVICE_GENERAL, 'General'),
        (SERVICE_PRIORITY, 'Priority'),
        (SERVICE_SUPPORT, 'Support'),
    ]

    STATUS_WAITING = 'WAITING'
    STATUS_SERVING = 'SERVING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_SERVING, 'Serving'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    token_number = models.PositiveIntegerField(unique=True)
    customer_name = models.CharField(max_length=100)
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_CHOICES,
        default=SERVICE_GENERAL,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_WAITING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'#{self.token_number} - {self.customer_name} ({self.status})'
