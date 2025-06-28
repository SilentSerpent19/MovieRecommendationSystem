# Movie Data Files

This directory contains the CSV files used by the Django movie recommendation app.

## Files

- **`movies_metadata.csv`** - Contains movie metadata including:
  - Title, release date, genres, ratings, and other movie information
  - Used by the `import_movies_kaggle.py` management command

- **`credits.csv`** - Contains cast and crew information including:
  - Actors, directors, and other crew members
  - Used by the `import_movies_kaggle.py` management command

## Usage

These files are automatically processed by the Django management command:
```bash
python manage.py import_movies_kaggle
```

This command merges both CSV files and imports the movie data into the Django database.

## Source

These files are from the Kaggle MovieLens dataset and are used to populate the movie database for the recommendation system. 