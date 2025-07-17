"""
URL configuration for complaint_system project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include('complaints.urls')),
]