from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Complaint, Comment, Staff, Student
from .forms import ComplaintForm, CommentForm, ComplaintStatusForm
from analysis.sentiment import ComplaintAnalyzer
from .forms import StudentRegistrationForm, StaffRegistrationForm



from django.contrib.auth import authenticate, login, logout

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from .models import Student, Staff
from django.views.decorators.csrf import csrf_protect

@login_required
def dashboard(request):
    """
    Main dashboard view that redirects to the appropriate dashboard 
    based on user type (student or staff)
    """
    # Check if user is a student
    try:
        student = Student.objects.get(user=request.user)
        return redirect('student_dashboard')
    except Student.DoesNotExist:
        pass
    
    # Check if user is staff
    try:
        staff = Staff.objects.get(user=request.user)
        return redirect('staff_dashboard')
    except Staff.DoesNotExist:
        pass
    
    # If user is neither student nor staff
    messages.error(request, "You do not have permission to access the dashboard.")
    return redirect('login')

@login_required
def student_dashboard(request):
    """Dashboard for students to view and submit complaints"""
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        messages.error(request, "You need a student account to access this page.")
        return redirect('login')
    
    # Get student's complaints
    complaints = Complaint.objects.filter(student=student).order_by('-created_at')
    
    # Handle complaint submission
    if request.method == 'POST':
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.student = student
            
            # Analyze complaint text with sentiment analysis
            analyzer = ComplaintAnalyzer()
            analysis_result = analyzer.analyze(
                complaint.description, 
                title=complaint.title
            )
            
            # Set the analyzed attributes
            complaint.category = analysis_result['category']
            complaint.priority = analysis_result['priority']
            complaint.sentiment_score = analysis_result['sentiment_score']
            complaint.save()
            
            # Assign staff members based on analysis
            for role in analysis_result['assigned_roles']:
                staff_members = Staff.objects.filter(role=role)
                for staff in staff_members:
                    complaint.assigned_to.add(staff)
            
            messages.success(request, "Your complaint has been submitted successfully.")
            return redirect('student_dashboard')
    else:
        form = ComplaintForm()
    
    context = {
        'student': student,
        'complaints': complaints,
        'form': form
    }
    return render(request, 'student_dashboard.html', context)

@login_required
def staff_dashboard(request):
    """Dashboard for staff to manage complaints"""
    try:
        staff = Staff.objects.get(user=request.user)
    except Staff.DoesNotExist:
        messages.error(request, "You need a staff account to access this page.")
        return redirect('login')
    
    # Get complaints assigned to this staff member
    assigned_complaints = staff.assigned_complaints.all().order_by('-priority', '-created_at')
    
    # Filter for VC and Registrar to see critical cases
    if staff.role in ['VC', 'REG']:
        critical_complaints = Complaint.objects.filter(priority='CRIT').order_by('-created_at')
    else:
        critical_complaints = Complaint.objects.none()
    
    # Combine and remove duplicates
    complaints = (assigned_complaints | critical_complaints).distinct()
    
    # Paginate results
    paginator = Paginator(complaints, 10)  # 10 complaints per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'staff': staff,
        'page_obj': page_obj,
        'is_vc_or_reg': staff.role in ['VC', 'REG']
    }
    return render(request, 'staff_dashboard.html', context)

@login_required
def complaint_detail(request, complaint_id):
    """View for seeing complaint details and adding comments"""
    complaint = get_object_or_404(Complaint, pk=complaint_id)
    
    # Check if user has permission to view this complaint
    user = request.user
    try:
        # If user is a student, they can only view their own complaints
        student = Student.objects.get(user=user)
        if complaint.student != student:
            return HttpResponseForbidden("You don't have permission to view this complaint.")
    except Student.DoesNotExist:
        try:
            # If user is staff, they can only view complaints assigned to them
            # or critical complaints if they are VC or Registrar
            staff = Staff.objects.get(user=user)
            is_assigned = complaint in staff.assigned_complaints.all()
            is_critical_and_authorized = complaint.is_critical() and staff.role in ['VC', 'REG']
            
            if not (is_assigned or is_critical_and_authorized):
                return HttpResponseForbidden("You don't have permission to view this complaint.")
        except Staff.DoesNotExist:
            return HttpResponseForbidden("You don't have permission to view this complaint.")
    
    # Handle comment submission
    if request.method == 'POST':
        try:
            staff = Staff.objects.get(user=user)
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.complaint = complaint
                comment.staff = staff
                comment.save()
                messages.success(request, "Your comment has been added.")
                
                # If comment added by VC or Registrar to critical complaint, update status
                if staff.role in ['VC', 'REG'] and complaint.is_critical():
                    complaint.status = 'REVW'  # Set to "Under Review"
                    complaint.save()
                
                return redirect('complaint_detail', complaint_id=complaint.id)
        except Staff.DoesNotExist:
            messages.error(request, "Only staff can comment on complaints.")
    else:
        form = CommentForm()
    
    # Get all comments for this complaint
    comments = Comment.objects.filter(complaint=complaint).order_by('created_at')
    
    # Determine if the current user is staff
    is_staff = hasattr(user, 'staff')
    
    # If user is staff, provide a form to update complaint status
    status_form = None
    if is_staff:
        if request.method == 'POST' and 'update_status' in request.POST:
            status_form = ComplaintStatusForm(request.POST, instance=complaint)
            if status_form.is_valid():
                status_form.save()
                messages.success(request, "Complaint status updated.")
                return redirect('complaint_detail', complaint_id=complaint.id)
        else:
            status_form = ComplaintStatusForm(instance=complaint)
    
    context = {
        'complaint': complaint,
        'comments': comments,
        'form': form,
        'status_form': status_form,
        'is_staff': is_staff,
        'is_vc_or_reg': is_staff and user.staff.role in ['VC', 'REG']
    }
    return render(request, 'complaint_detail.html', context)


#############################################################################

def account_type_selection(request):
    """View to let users choose between student and staff registration"""
    return render(request, 'accounts/account_type_selection.html')

@csrf_protect
def login_view(request):
    """Handle user login for both students and staff"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.get_full_name() or username}!")
                
                # Redirect to the appropriate dashboard
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')

def register_student_view(request):
    """
    Registration view for students
    This would typically be handled by administrative staff,
    but included here for demonstration purposes
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Student account created successfully for {user.username}!")
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'accounts/register_student.html', {'form': form})

def register_staff_view(request):
    """
    Registration view for staff
    This would typically be handled by administrative staff,
    but included here for demonstration purposes
    """
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Staff account created successfully for {user.username}!")
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StaffRegistrationForm()
    
    return render(request, 'accounts/register_staff.html', {'form': form})