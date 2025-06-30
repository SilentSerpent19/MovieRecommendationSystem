from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

# Create your models here.
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("dev", "Developer"),
        ("pm", "Project Manager"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="dev")

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    

class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="employee", on_delete=models.CASCADE)
    position = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.position or "Employee"}'

class Project(models.Model):
    employees = models.ManyToManyField(Employee, related_name="projects")
    name = models.CharField(max_length=100)
    description = models.TextField()
    upwork_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=[
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived")
    ], default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Task(models.Model):
    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    main_employee = models.ForeignKey(Employee, related_name="main_tasks", on_delete=models.CASCADE)
    pair_employee = models.ForeignKey(Employee, related_name="pair_tasks", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("blocked", "Blocked")
    ], default="todo")
    description = models.TextField()
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=[
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical")
    ], default="medium")
    story_points = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.project.name})'

class Comment(models.Model):
    task = models.ForeignKey(Task, related_name="comments", on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, related_name="comments", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.employee.user.username} on {self.task.name}'

class SyncLog(models.Model):
    project = models.ForeignKey(Project, related_name="sync_logs", on_delete=models.CASCADE)
    synced_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ("success", "Success"),
        ("failed", "Failed")
    ], default="success")
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'SyncLog for {self.project.name} at {self.synced_at} ({self.status})'