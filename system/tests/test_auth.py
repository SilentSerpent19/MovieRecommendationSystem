import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_registration_creates_user_and_logs_in(client):
    response = client.post('/register/', {
        'username': 'newuser',
        'email': 'new@example.com',
        'password1': 'a-Strong-pass-123',
        'password2': 'a-Strong-pass-123',
    })
    assert response.status_code == 302
    assert User.objects.filter(username='newuser').exists()


@pytest.mark.django_db
def test_login_redirects_to_recommend(client):
    User.objects.create_user(username='testuser', password='testpass')
    response = client.post('/login/', {'username': 'testuser', 'password': 'testpass'})
    assert response.status_code == 302
    assert response.url == '/recommend/'
