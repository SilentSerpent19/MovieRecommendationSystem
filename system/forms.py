from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from system.models import Genre, Mood
from system.recommender import ERAS, Filters

RATING_CHOICES = [('', 'Any'), ('6', '6+'), ('7', '7+'), ('8', '8+')]


class RecommendationForm(forms.Form):
    genre = forms.ChoiceField(choices=[], required=False)
    era = forms.ChoiceField(choices=[('', 'Any')] + [(e, e) for e in ERAS], required=False)
    rating = forms.ChoiceField(choices=RATING_CHOICES, required=False, label='IMDb rating')
    mood = forms.ChoiceField(choices=[], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['genre'].choices = [('', 'Any')] + [(g, g) for g in Genre.objects.values_list('name', flat=True)]
        self.fields['mood'].choices = [('', 'Any')] + [(m, m) for m in Mood.objects.values_list('name', flat=True)]

    def to_filters(self) -> Filters:
        cd = self.cleaned_data
        return Filters(genre=cd['genre'], era=cd['era'],
                       min_rating=float(cd['rating']) if cd['rating'] else None, mood=cd['mood'])


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email address'
    }))

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': f'Enter your {field_name.replace("_", " ")}'
            })
            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Choose a username'
            elif field_name == 'password1':
                field.widget.attrs['placeholder'] = 'Create a password'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Confirm your password'

class EditProfileForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Current Password', 'class': 'form-control'}),
        label='Current Password', required=True,
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'}),
        label='Username', required=False,
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email', 'class': 'form-control'}),
        label='Email', required=False,
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New Password', 'class': 'form-control'}),
        label='New Password', required=False,
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm New Password', 'class': 'form-control'}),
        label='Confirm New Password', required=False,
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise ValidationError('Current password is incorrect.')
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        email = cleaned_data.get('email')
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if not username and not email and not new_password1:
            raise ValidationError('You must change at least one field.')

        if username and User.objects.exclude(pk=self.user.pk).filter(username=username).exists():
            self.add_error('username', 'This username is already taken.')
        if email and User.objects.exclude(pk=self.user.pk).filter(email=email).exists():
            self.add_error('email', 'This email is already in use.')
        if new_password1 or new_password2:
            if new_password1 != new_password2:
                self.add_error('new_password2', 'Passwords do not match.')
            if new_password1 and len(new_password1) < 8:
                self.add_error('new_password1', 'Password must be at least 8 characters.')
        return cleaned_data
