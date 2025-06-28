from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.mail import send_mail
from system.models import Movie
import random

class Command(BaseCommand):
    help = 'Send weekly movie recommendations to all users (stub).'

    def handle(self, *args, **options):
        users = User.objects.all()
        sample_movies = list(Movie.objects.all())
        for user in users:
            if not user.email:
                continue
            recs = random.sample(sample_movies, min(3, len(sample_movies)))
            movie_list = '\n'.join([f"- {m.title} ({m.year})" for m in recs])
            send_mail(
                'Your Weekly Movie Recommendations',
                f'Hi {user.username},\n\nHere are your weekly movie picks:\n{movie_list}\n\nEnjoy!\n',
                'noreply@example.com',
                [user.email],
                fail_silently=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Sent recs to {user.email}')) 