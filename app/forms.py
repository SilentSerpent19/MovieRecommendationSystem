from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Project, Task, Comment, Employee

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ("username", "email", "role", "password1", "password2")
        widgets = {
            "role": forms.Select(attrs={"class": "form-control"}),
        }

class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = CustomUser
        fields = ("username", "password")

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ("user", "position", "phone_number", "department", "is_active", "profile_picture")
        widgets = {
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(),
        } 

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description", "upwork_id", "status", "employees")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "employees": forms.SelectMultiple(attrs={"class": "form-control"}),
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ("project", "main_employee", "pair_employee", "name", "status", "description", "due_date", "priority", "story_points")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(attrs={"rows": 2}),
        }

