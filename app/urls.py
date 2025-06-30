from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('', views.home, name='home'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('projects/<int:project_pk>/tasks/', views.task_list, name='task_list'),
    path('projects/<int:project_pk>/tasks/create/', views.task_create, name='task_create'),
    path('projects/<int:project_pk>/tasks/<int:task_pk>/edit/', views.task_edit, name='task_edit'),
    path('projects/<int:project_pk>/tasks/<int:task_pk>/comments/', views.comment_list, name='comment_list'),
    path('projects/<int:project_pk>/tasks/<int:task_pk>/comments/add/', views.comment_create, name='comment_create'),
    path('projects/<int:project_pk>/tasks/<int:task_pk>/comments/<int:comment_pk>/edit/', views.comment_edit, name='comment_edit'),
    path('projects/<int:project_pk>/tasks/<int:task_pk>/comments/<int:comment_pk>/delete/', views.comment_delete, name='comment_delete'),
]
