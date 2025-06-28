from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import SubscriptionPlan, UserSubscription, Movie

# Create your tests here.

class BasicFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass', email='test@example.com')
        self.plan = SubscriptionPlan.objects.create(name='Basic', price=0, description='Free plan')
        Movie.objects.create(title='Test Movie', year='2000', genre='Action', imdb_rating=8.0)

    def test_registration(self):
        response = self.client.post('/register/', {'username': 'newuser', 'password1': 'newpass123', 'password2': 'newpass123'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login(self):
        response = self.client.post('/login/', {'username': 'testuser', 'password': 'testpass'})
        self.assertEqual(response.status_code, 302)

    def test_recommendation_access(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get('/recommend/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Movie Recommendation')

    def test_subscribe_flow(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.post('/subscribe/', {'plan_id': self.plan.id})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UserSubscription.objects.filter(user=self.user, plan=self.plan, active=True).exists())
