from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class EditProfileForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Current Password', 'class': 'form-control'}), label='Current Password', required=True)
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'}), label='Username', required=False)
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email', 'class': 'form-control'}), label='Email', required=False)
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'New Password', 'class': 'form-control'}), label='New Password', required=False)
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm New Password', 'class': 'form-control'}), label='Confirm New Password', required=False)

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