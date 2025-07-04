from django.core.management.base import BaseCommand
from system.models import Movie, Mood

GENRE_TO_MOODS = {
    'comedy': ['Funny', 'Feel-Good'],
    'romance': ['Romantic', 'Uplifting'],
    'horror': ['Scary', 'Dark'],
    'thriller': ['Suspenseful', 'Mysterious'],
    'action': ['Action-Packed', 'Excited'],
    'adventure': ['Adventurous', 'Excited'],
    'animation': ['Feel-Good', 'Funny'],
    'family': ['Feel-Good', 'Uplifting'],
    'drama': ['Thought-Provoking', 'Sad'],
    'mystery': ['Mysterious', 'Suspenseful'],
    'crime': ['Mysterious', 'Dark', 'Suspenseful'], 
    'fantasy': ['Excited', 'Adventurous'],
    'sci-fi': ['Excited', 'Thought-Provoking'],
    'science fiction': ['Excited', 'Thought-Provoking'],
    'documentary': ['Inspiring', 'Thought-Provoking'],
    'music': ['Uplifting', 'Feel-Good'],
    'musical': ['Uplifting', 'Feel-Good'],
    'war': ['Dark', 'Thought-Provoking'],
    'history': ['Thought-Provoking', 'Inspiring'],
    'western': ['Adventurous', 'Action-Packed'],
    'biography': ['Inspiring', 'Thought-Provoking'],
    'sport': ['Excited', 'Uplifting'],
    'superhero': ['Action-Packed', 'Excited'],
    'super hero': ['Action-Packed', 'Excited'],
    'super-hero': ['Action-Packed', 'Excited'],
}

class Command(BaseCommand):
    help = 'Assign moods to movies based on genre keywords with improved logic.'

    def handle(self, *args, **options):
        assigned = 0
        default_mood = Mood.objects.filter(name='Thought-Provoking').first()
        
        for movie in Movie.objects.all():
            if movie.mood:
                continue 
                
            genre_str = (movie.genre or '').lower()
            found = False
            
            if genre_str:
                matching_moods = []
                for genre_key, mood_names in GENRE_TO_MOODS.items():
                    if genre_key in genre_str:
                        matching_moods.extend(mood_names)
                
                if matching_moods:
                    unique_moods = list(set(matching_moods))
                    available_moods = [Mood.objects.filter(name=mood_name).first() for mood_name in unique_moods]
                    available_moods = [m for m in available_moods if m]
                    
                    if available_moods:
                        selected_mood = self.select_best_mood(movie, available_moods)
                        movie.mood = selected_mood
                        movie.save()
                        assigned += 1
                        found = True
            
            if not found and default_mood:
                movie.mood = default_mood
                movie.save()
                assigned += 1
                
        self.stdout.write(self.style.SUCCESS(f'Assigned moods to {assigned} movies.'))
    
    def select_best_mood(self, movie, available_moods):
        """Select the best mood based on movie characteristics."""
        if len(available_moods) == 1:
            return available_moods[0]
        
        if 'crime' in (movie.genre or '').lower():
            mysterious_mood = next((m for m in available_moods if m.name == 'Mysterious'), None)
            if mysterious_mood:
                return mysterious_mood
        
        if movie.imdb_rating and movie.imdb_rating >= 7.5:
            positive_moods = ['Feel-Good', 'Uplifting', 'Inspiring', 'Excited']
            for mood_name in positive_moods:
                mood = next((m for m in available_moods if m.name == mood_name), None)
                if mood:
                    return mood
        
        if movie.year and movie.year.isdigit() and int(movie.year) < 1980:
            classic_moods = ['Thought-Provoking', 'Inspiring', 'Mysterious']
            for mood_name in classic_moods:
                mood = next((m for m in available_moods if m.name == mood_name), None)
                if mood:
                    return mood
        
        return available_moods[0] 