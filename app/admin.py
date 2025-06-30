from django.contrib import admin
from app.models import CustomUser, Employee, Project, Task, Comment, SyncLog

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Employee)
admin.site.register(Project)
admin.site.register(Task)
admin.site.register(Comment)
admin.site.register(SyncLog)
