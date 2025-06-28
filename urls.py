from django.contrib import admin
from django.urls import path, include, re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('system.api_urls')),
    path('', include('system.urls')),  # Include system app URLs
] 