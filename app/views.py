from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.http import require_POST
from .models import Project, Employee, Task
from .forms import ProjectForm, TaskForm, CommentForm
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def home(request):
    # Add today's date for overdue task calculations
    user = request.user
    employee = user.employee
    
    # Calculate in-progress tasks count
    in_progress_count = employee.main_tasks.filter(status='in_progress').count()
    
    # Calculate overdue tasks count
    overdue_count = 0
    for task in employee.main_tasks.all():
        if task.due_date and task.due_date < timezone.now().date() and task.status != 'done':
            overdue_count += 1
    
    context = {
        'today': timezone.now().date(),
        'in_progress_count': in_progress_count,
        'overdue_count': overdue_count,
    }
    return render(request, 'home.html', context)

@login_required
def project_list(request):
    user = request.user
    employee = user.employee
    
    # Get all projects
    projects = Project.objects.all()
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Calculate statistics
    total_projects = projects.count()
    active_projects = projects.filter(status='active').count()
    completed_projects = projects.filter(status='completed').count()
    on_hold_projects = projects.filter(status='on_hold').count()
    
    context = {
        'projects': projects,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'on_hold_projects': on_hold_projects,
    }
    return render(request, 'project_list.html', context)

@login_required
def project_create(request):
    user = request.user
    if user.role != 'pm':
        return HttpResponseForbidden('You do not have permission to create projects.')
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            # Optionally assign the creator as a project manager/employee
            employee = user.employee
            project.employees.add(employee)
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('project_list')
    else:
        form = ProjectForm()
    return render(request, 'project_form.html', {'form': form})

@login_required
def project_edit(request, pk):
    user = request.user
    project = get_object_or_404(Project, pk=pk)
    employee = user.employee
    if user.role != 'pm' or employee not in project.employees.all():
        return HttpResponseForbidden('You do not have permission to edit this project.')
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated successfully!')
            return redirect('project_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'project_form.html', {'form': form, 'edit': True})

@login_required
def project_delete(request, pk):
    user = request.user
    project = get_object_or_404(Project, pk=pk)
    employee = user.employee
    if user.role != 'pm' or employee not in project.employees.all():
        return HttpResponseForbidden('You do not have permission to delete this project.')
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('project_list')
    return render(request, 'project_confirm_delete.html', {'project': project})

@login_required
def task_list(request, project_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    
    # Check if user has access to this project
    if user.role == 'pm':
        # Project Managers: see all tasks in the project
        tasks = project.tasks.all()
    elif user.role == 'dev':
        # Developers: see only their assigned tasks in the project
        tasks = project.tasks.filter(
            Q(main_employee=employee) | Q(pair_employee=employee)
        )
    else:
        tasks = project.tasks.none()
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        tasks = tasks.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    # Apply priority filter
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Apply assignee filter
    assignee_filter = request.GET.get('assignee', '')
    if assignee_filter:
        tasks = tasks.filter(
            Q(main_employee__user__username__icontains=assignee_filter) |
            Q(pair_employee__user__username__icontains=assignee_filter)
        )
    
    # Calculate statistics
    total_tasks = tasks.count()
    todo_count = tasks.filter(status='todo').count()
    in_progress_count = tasks.filter(status='in_progress').count()
    done_count = tasks.filter(status='done').count()
    
    # Calculate overdue tasks
    overdue_count = 0
    for task in tasks:
        if task.due_date and task.due_date < timezone.now().date() and task.status != 'done':
            overdue_count += 1
    
    context = {
        'project': project,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assignee_filter': assignee_filter,
        'total_tasks': total_tasks,
        'todo_count': todo_count,
        'in_progress_count': in_progress_count,
        'done_count': done_count,
        'overdue_count': overdue_count,
    }
    return render(request, 'task_list.html', context)

@login_required
def task_create(request, project_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    if user.role != 'pm' or employee not in project.employees.all():
        return HttpResponseForbidden('You do not have permission to create tasks in this project.')
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            form.save()
            messages.success(request, f'Task "{task.name}" created successfully!')
            return redirect('task_list', project_pk=project.pk)
    else:
        form = TaskForm()
    return render(request, 'task_form.html', {'form': form, 'project': project})

@login_required
def task_edit(request, project_pk, task_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if user.role != 'pm' or employee not in project.employees.all():
        return HttpResponseForbidden('You do not have permission to edit this task.')
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f'Task "{task.name}" updated successfully!')
            return redirect('task_list', project_pk=project.pk)
    else:
        form = TaskForm(instance=task)
    return render(request, 'task_form.html', {'form': form, 'project': project, 'edit': True})

@login_required
def comment_list(request, project_pk, task_pk):
    user = request.user
    # Ensure employee object exists
    employee, created = Employee.objects.get_or_create(user=user)
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if employee not in project.employees.all():
        return HttpResponseForbidden('You do not have access to this task.')
    comments = task.comments.all().order_by('created_at')
    comment_form = CommentForm()
    
    # Add debugging info
    print(f"Task: {task.name}")
    print(f"Comments count: {comments.count()}")
    for comment in comments:
        print(f"Comment: {comment.content} by {comment.employee.user.username}")
    
    return render(request, 'comment_list.html', {
        'project': project, 
        'task': task, 
        'comments': comments,
        'comment_form': comment_form
    })

@login_required
def comment_create(request, project_pk, task_pk):
    user = request.user
    # Ensure employee object exists
    employee, created = Employee.objects.get_or_create(user=user)
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if employee not in project.employees.all():
        return HttpResponseForbidden('You do not have access to comment on this task.')
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.employee = employee
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('comment_list', project_pk=project.pk, task_pk=task.pk)
        else:
            # Add error message for debugging
            messages.error(request, f'Form errors: {form.errors}')
    else:
        form = CommentForm()
    return render(request, 'comment_form.html', {'form': form, 'project': project, 'task': task})

@login_required
def comment_edit(request, project_pk, task_pk, comment_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    comment = get_object_or_404(task.comments, pk=comment_pk)
    if not (employee == comment.employee or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to edit this comment.')
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Comment updated successfully!')
            return redirect('comment_list', project_pk=project.pk, task_pk=task.pk)
    else:
        form = CommentForm(instance=comment)
    return render(request, 'comment_form.html', {'form': form, 'project': project, 'task': task, 'edit': True})

@login_required
def comment_delete(request, project_pk, task_pk, comment_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    comment = get_object_or_404(task.comments, pk=comment_pk)
    if not (employee == comment.employee or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to delete this comment.')
    if request.method == 'POST':
        comment.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('comment_list', project_pk=project.pk, task_pk=task.pk)
    return render(request, 'comment_confirm_delete.html', {'comment': comment, 'project': project, 'task': task})


