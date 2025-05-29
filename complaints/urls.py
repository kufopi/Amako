from django.urls import path
from . import views

urlpatterns = [
    # Main dashboard redirecting based on user type
    path('', views.dashboard, name='dashboard'),
    
    # Student dashboard
    path('student/', views.student_dashboard, name='student_dashboard'),
    
    # Staff dashboard
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    
    # Complaint detail view
    path('complaint/<int:complaint_id>/', views.complaint_detail, name='complaint_detail'),
    
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.account_type_selection, name='register'),
    path('register/student/', views.register_student_view, name='register_student'),
    path('register/staff/', views.register_staff_view, name='register_staff'),   
]