from getpass import getpass

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError


class Command(BaseCommand):
    help = 'Create a staff account that can sign in to the QueueLess counter.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--email', default='')
        parser.add_argument('--first-name', default='')
        parser.add_argument('--last-name', default='')

    def handle(self, *args, **options):
        username = options['username'].strip()
        if not username:
            raise CommandError('username cannot be empty.')

        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(f'User "{username}" already exists.')

        password = getpass('Password: ')
        confirmation = getpass('Confirm password: ')
        if password != confirmation:
            raise CommandError('Passwords do not match.')

        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError(str(error)) from error

        user = User.objects.create_user(
            username=username,
            password=password,
            email=options['email'],
            first_name=options['first_name'],
            last_name=options['last_name'],
        )
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        self.stdout.write(
            self.style.SUCCESS(f'Staff account "{username}" created.')
        )
