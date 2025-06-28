from django.core.management.base import BaseCommand
from system.models import Mood

class Command(BaseCommand):
    help = 'Add common moods to the Mood table.'

    def handle(self, *args, **options):
        moods = [
            'Happy', 'Sad', 'Excited', 'Romantic', 'Scary', 'Adventurous',
            'Chill', 'Inspiring', 'Mysterious', 'Funny', 'Dark', 'Uplifting',
            'Action-Packed', 'Thought-Provoking', 'Feel-Good', 'Suspenseful'
        ]
        created = 0
        for mood_name in moods:
            mood, was_created = Mood.objects.get_or_create(name=mood_name)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Added {created} new moods.')) 