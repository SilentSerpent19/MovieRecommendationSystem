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


@pytest.mark.django_db
def test_api_register_sets_a_usable_password(client):
    response = client.post('/api/register/', {'username': 'apiuser', 'email': 'api@example.com',
                                              'password': 'a-Strong-pass-123'})
    assert response.status_code == 201
    assert 'password' not in response.json()
    assert User.objects.get(username='apiuser').check_password('a-Strong-pass-123')
    assert client.post('/api/login/', {'username': 'apiuser', 'password': 'a-Strong-pass-123'}).json()['success']


@pytest.mark.django_db
def test_api_register_rejects_weak_or_missing_password(client):
    assert client.post('/api/register/', {'username': 'u1', 'email': 'u1@example.com'}).status_code == 400
    assert client.post('/api/register/', {'username': 'u2', 'email': 'u2@example.com',
                                          'password': '123'}).status_code == 400
    assert not User.objects.filter(username__in=['u1', 'u2']).exists()
