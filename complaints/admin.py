from django.contrib import admin
from .models import *  # Import all models from this app

# Register all models in the admin site
for model in [Complaint,Comment,Student,Staff]:
    admin.site.register(model)
