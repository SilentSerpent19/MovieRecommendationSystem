from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from system.recommender import Filters, recommend


class Command(BaseCommand):
    help = 'Email each user with an address their top 5 personalised recommendations.'

    def handle(self, *args, **options):
        sent = 0
        for user in User.objects.exclude(email=''):
            result = recommend(user, Filters(), k=5, log_request=False)
            if not result.items:
                continue
            lines = '\n'.join(f'- {r.movie} - {r.reason}' for r in result.items)
            send_mail('Your weekly movie picks',
                      f'Hi {user.username},\n\nHere are this week\'s picks for you:\n{lines}\n\nEnjoy!\n',
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'Sent recommendations to {sent} users.'))
