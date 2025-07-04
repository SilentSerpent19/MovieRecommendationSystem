# Movie Recommendation System

## Overview
A robust Django-based web application for personalized movie recommendations, leveraging real-world data from Kaggle, with mood-based filtering, user profiles, subscription management, analytics, and PayPal integration.

---

## Features
- **Personalized Recommendations:** Mood, genre, era, and rating-based movie suggestions.
- **Kaggle Data Integration:** Import and process large movie datasets from Kaggle.
- **Mood Assignment:** Automated mood tagging for movies using genre and metadata.
- **User Management:** Registration, login, profile editing.
- **Subscription Plans:** Free, Premium, and Pro plans with PayPal payment integration.
- **Analytics Dashboard:** Admin insights on user activity and movie trends.
- **REST API:** Extensible endpoints for integration with other platforms.
- **GDPR & Security:** Environment-based config, secure cookies, CORS, and GDPR compliance.

---

## Tech Stack
- **Backend:** Django 5.2.1, Django REST Framework
- **Database:** SQLite (default), Postgres/MySQL ready
- **Frontend:** Django Templates (HTML/CSS)
- **Data Sources:** Kaggle (movies_metadata.csv, credits.csv)
- **Payments:** PayPal
- **Other:** django-environ, CORS, django-extensions

---

## Data Pipeline: From Kaggle to Recommendations
1. **Import Kaggle Data:**
   - Place `movies_metadata.csv` and `credits.csv` in the `data/` directory.
   - Run: `python manage.py import_movies_kaggle`
   - Cleans, merges, and imports up to 5000 high-quality movies into the database.
2. **Assign Moods:**
   - Run: `python manage.py assign_moods`
   - Tags each movie with a mood (e.g., Uplifting, Dark, Funny) based on genre and metadata.
3. **User Interaction:**
   - Users select mood, genre, era, and rating to receive tailored recommendations.

---

## Mood-Based Recommendation Logic
- Each user choice (mood, genre, era, rating) acts as a branch in a decision tree.
- The system filters movies step by step, relaxing criteria if needed, and ranks results by a smart scoring function.
- Moods are assigned using a mapping from genres to moods, with additional logic for rating and year.

---

## Setup & Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/decision-tree-movie-recs.git
   cd decision-tree-movie-recs
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and set your secrets (see `decision/settings.py` for required variables).
5. **Apply migrations:**
   ```bash
   python manage.py migrate
   ```
6. **Import Kaggle data and assign moods:**
   ```bash
   python manage.py import_movies_kaggle
   python manage.py assign_moods
   ```
7. **Create a superuser (admin):**
   ```bash
   python manage.py createsuperuser
   ```
8. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

---

## Usage
- Register a new user or log in.
- Use the recommendation form to filter by mood, genre, era, and rating.
- Premium users can access advanced filters and unlimited recommendations.
- Admins can view analytics and manage users/movies via the Django admin panel.

---

## API Endpoints
- **/api/recommend/** – Get movie recommendations (requires authentication)
- **/api/register/** – Register a new user
- **/api/login/** – Log in
- (See `system/api_views.py` for more)

---

## Contribution Guidelines
1. Fork the repository and create your branch (`git checkout -b feature/YourFeature`)
2. Commit your changes (`git commit -am 'Add new feature'`)
3. Push to the branch (`git push origin feature/YourFeature`)
4. Open a Pull Request

---

## License
[MIT License](LICENSE)

---
