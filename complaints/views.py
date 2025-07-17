# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Complaint, Comment, Staff, Student, Department
from .forms import ComplaintForm, CommentForm, StatusUpdateForm
from analysis.sentiment import ComplaintAnalyzer
from .forms import StudentRegistrationForm, StaffRegistrationForm

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect

@login_required
def dashboard(request):
    """Main dashboard that redirects based on user type"""
    if hasattr(request.user, 'student'):
        return redirect('student_dashboard')

    # Check if the user has a staff profile
    if hasattr(request.user, 'staff'):
        staff_profile = request.user.staff
        if staff_profile.role == 'WD':
            return redirect('works_dashboard')
        return redirect('staff_dashboard')

    # If the user is authenticated but has neither a student nor a staff profile
    messages.warning(request, "Your account type is not yet set up. Please select your role.")
    return redirect('register')

@login_required
def student_dashboard(request):
    """Dashboard for students to view their complaints"""
    try:
        student = request.user.student
    except:
        messages.error(request, "You need a student account to access this page")
        return redirect('login')
    
    complaints = Complaint.objects.filter(student=student).order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    
    if status_filter:
        # Handle comma-separated status values for grouped filters
        if ',' in status_filter:
            status_list = status_filter.split(',')
            complaints = complaints.filter(status__in=status_list)
        else:
            complaints = complaints.filter(status=status_filter)
    
    if priority_filter:
        complaints = complaints.filter(priority=priority_filter)
    if category_filter:
        complaints = complaints.filter(category=category_filter)
    
    # Pagination
    paginator = Paginator(complaints, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics for dashboard
    stats = {
        'total_count': Complaint.objects.filter(student=student).count(),
        'pending_count': Complaint.objects.filter(student=student, status='PEND').count(),
        'in_progress_count': Complaint.objects.filter(student=student, status__in=['REVW', 'ASSG', 'PROG']).count(),
        'resolved_count': Complaint.objects.filter(student=student, status='RESV').count(),
        'closed_count': Complaint.objects.filter(student=student, status='CLSD').count(),
        'critical_count': Complaint.objects.filter(student=student, priority='CRIT').count(),
    }
    
    # Add filter context for template highlighting
    current_filters = {
        'status': status_filter,
        'priority': priority_filter,
        'category': category_filter,
    }
    
    return render(request, 'student_dashboard.html', {
        'student': student,
        'page_obj': page_obj,
        'stats': stats,
        'current_filters': current_filters,
    })

@login_required
def submit_complaint(request):
    """Enhanced view for students to submit new complaints with automatic assignment and tracking"""
    try:
        student = request.user.student
    except:
        messages.error(request, "You need a student account to submit complaints")
        return redirect('login')
    
    if request.method == 'POST':
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.student = student
            
            # Analyze complaint text
            analyzer = ComplaintAnalyzer()
            analysis = analyzer.analyze(complaint.description, complaint.title)
            
            complaint.category = analysis['category']
            complaint.priority = analysis['priority']
            complaint.sentiment_score = analysis['sentiment_score']
            
            # Enhanced priority logic for academic complaints
            if complaint.category == 'ACAD':
                # Check for exam-related urgency keywords
                urgency_keywords = ['exam', 'test', 'weeks', 'days', 'assessment', 'evaluation']
                complaint_text = (complaint.title + ' ' + complaint.description).lower()
                
                if any(keyword in complaint_text for keyword in urgency_keywords):
                    # Extract time mentions and assess urgency
                    if any(phrase in complaint_text for phrase in ['3 weeks', 'two weeks', '2 weeks', 'few weeks']):
                        complaint.priority = 'HIGH'
                    elif any(phrase in complaint_text for phrase in ['week', 'days', 'soon']):
                        complaint.priority = 'CRIT'
                    elif complaint.priority == 'LOW':
                        complaint.priority = 'MED'
            
            # Save complaint first to get an ID
            complaint.save()
            
            # Enhanced assignment and tracking logic
            assign_complaint_to_department(complaint)
            setup_complaint_tracking(complaint)
            
            messages.success(request, 
                f"Complaint submitted successfully! "
                f"Priority: {complaint.get_priority_display()}, "
                f"Assigned to: {complaint.assigned_to.get_role_display() if complaint.assigned_to else 'Pending'}"
            )
            return redirect('student_dashboard')
    else:
        form = ComplaintForm()
    
    return render(request, 'submit_complaint.html', {'form': form})

def assign_complaint_to_department(complaint):
    """Enhanced assignment logic based on category and context"""
    assigned_staff = None
    
    # Infrastructure complaints
    if complaint.category == 'INFRA':
        # All infrastructure issues go to Works Department
        assigned_staff = Staff.objects.filter(role='WD').first()
        
    # Hostel complaints
    elif complaint.category == 'HOSTEL':
        # All hostel issues go to Hall Warden
        assigned_staff = Staff.objects.filter(role='HW').first()
        
    # Safety complaints
    elif complaint.category == 'SAFETY':
        # Safety issues go to Student Affairs
        assigned_staff = Staff.objects.filter(role='SA').first()
        
    # Harassment complaints
    elif complaint.category == 'HARASS':
        # Harassment issues go to Student Affairs
        assigned_staff = Staff.objects.filter(role='SA').first()
        
    # Academic complaints
    elif complaint.category == 'ACAD':
        # Academic issues go to student's HOD
        assigned_staff = Staff.objects.filter(
            role='HOD', 
            department=complaint.student.department
        ).first()
    
    if assigned_staff:
        complaint.assigned_to = assigned_staff
        complaint.status = 'ASSG'
        complaint.save(update_fields=['assigned_to', 'status'])

def setup_complaint_tracking(complaint):
    """Enhanced tracking logic based on complaint type and priority"""
    trackers_to_add = []
    
    # Critical and High priority complaints are always tracked by VC and Registrar
    if complaint.priority in ['HIGH', 'CRIT']:
        vc = Staff.objects.filter(role='VC').first()
        reg = Staff.objects.filter(role='REG').first()
        if vc:
            trackers_to_add.append(vc)
        if reg:
            trackers_to_add.append(reg)
    
    # Special tracking rules based on category and location
    
    # Infrastructure complaints in hostel - Hall Warden tracks (Works Dept handles)
    if complaint.category == 'INFRA' and (
        complaint.location_type == 'HOSTEL' or 
        (complaint.location and 'hostel' in complaint.location.lower())
    ):
        hw = Staff.objects.filter(role='HW').first()
        if hw and hw not in trackers_to_add:
            trackers_to_add.append(hw)
    
    # Infrastructure complaints in lecture rooms/labs - Student's HOD tracks
    elif complaint.category == 'INFRA' and (
        complaint.location_type in ['LECTURE', 'LAB'] or
        (complaint.location and any(term in complaint.location.lower() 
                                 for term in ['lecture', 'classroom', 'lab', 'laboratory']))
    ):
        hod = Staff.objects.filter(
            role='HOD', 
            department=complaint.student.department
        ).first()
        if hod and hod not in trackers_to_add:
            trackers_to_add.append(hod)
    
    # Harassment/Safety complaints - Student's HOD tracks (Student Affairs handles)
    elif complaint.category in ['HARASS', 'SAFETY']:
        hod = Staff.objects.filter(
            role='HOD', 
            department=complaint.student.department
        ).first()
        if hod and hod not in trackers_to_add:
            trackers_to_add.append(hod)
    
    # Hostel complaints - Student's HOD also tracks (Hall Warden handles)
    elif complaint.category == 'HOSTEL':
        hod = Staff.objects.filter(
            role='HOD', 
            department=complaint.student.department
        ).first()
        if hod and hod not in trackers_to_add:
            trackers_to_add.append(hod)
    
    # Academic complaints - Only student's HOD handles (no additional trackers needed)
    # The HOD is already assigned as the handler
    
    # Add all trackers
    for tracker in trackers_to_add:
        complaint.trackers.add(tracker)

@login_required
def complaint_detail(request, complaint_id):
    """Enhanced detailed view of a complaint with proper access control"""
    complaint = get_object_or_404(Complaint, pk=complaint_id)
    user = request.user

    # Check if user has permission to view this complaint
    if not complaint.can_user_view(user):
        messages.error(request, "You don't have permission to view this complaint")
        return redirect('dashboard')

    # Determine user type and permissions
    is_staff = hasattr(user, 'staff')
    is_student = hasattr(user, 'student')
    is_assigned_staff = is_staff and user.staff == complaint.assigned_to
    is_tracker = is_staff and user.staff in complaint.trackers.all()
    is_hod = is_staff and user.staff.role == 'HOD'

    if request.method == 'POST':
        if 'comment' in request.POST:
            if not is_staff:
                messages.error(request, "Only staff can add comments")
                return redirect('complaint_detail', complaint_id=complaint.id)
            
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.complaint = complaint
                comment.author = user.staff
                comment.save()
                
                # Auto-update status when assigned staff first comments
                if is_assigned_staff and complaint.status == 'ASSG':
                    complaint.status = 'PROG'
                    complaint.save()
                    messages.success(request, "Comment added and status updated to 'In Progress'")
                else:
                    messages.success(request, "Comment added successfully")
                
                # Send notification to student about the update
                send_complaint_notification(complaint, f"New comment added by {user.staff.get_role_display()}")
                
                return redirect('complaint_detail', complaint_id=complaint.id)
        
        elif 'status' in request.POST:
            # Only assigned staff can update status
            if not is_assigned_staff:
                messages.error(request, "Only the assigned staff member can update complaint status")
                return redirect('complaint_detail', complaint_id=complaint.id)
            
            status_form = StatusUpdateForm(request.POST)
            if status_form.is_valid():
                old_status = complaint.status
                new_status = status_form.cleaned_data['status']
                complaint.status = new_status
                complaint.save()
                
                # Add automatic comment for status change
                Comment.objects.create(
                    complaint=complaint,
                    author=user.staff,
                    content=f"Status changed from {complaint.get_status_display()} to {dict(complaint.STATUS_CHOICES)[new_status]}",
                    is_internal=False
                )
                
                messages.success(request, f"Complaint status updated to {complaint.get_status_display()}")
                
                # Send notification
                send_complaint_notification(complaint, f"Status updated to {complaint.get_status_display()}")
                
                return redirect('complaint_detail', complaint_id=complaint.id)

        # ==================== NEW STUDENT ACTION HANDLING CODE ====================
        elif 'student_action' in request.POST:
            # Only students can perform these actions on their own complaints
            if not is_student or complaint.student != request.user.student:
                messages.error(request, "You don't have permission to perform this action")
                return redirect('complaint_detail', complaint_id=complaint.id)
            
            action = request.POST.get('student_action')
            
            if action == 'request_update':
                update_request_content = request.POST.get('update_request_content', '').strip()
                if update_request_content:
                    # Create a comment from the student requesting update
                    Comment.objects.create(
                        complaint=complaint,
                        author=None,  # Student comment
                        content=f"Student requested update: {update_request_content}",
                        is_internal=False
                    )
                    
                    # Send notification to assigned staff
                    if complaint.assigned_to:
                        send_complaint_notification(
                            complaint, 
                            f"Student {complaint.student.user.get_full_name()} requested an update"
                        )
                    
                    messages.success(request, "Update request sent to assigned staff")
                else:
                    messages.error(request, "Please provide a message with your update request")
            
            elif action == 'mark_resolved':
                if complaint.status == 'PROG':
                    complaint.status = 'RESV'
                    complaint.save()
                    
                    # Add automatic comment
                    Comment.objects.create(
                        complaint=complaint,
                        author=None,  # Student comment
                        content="Student marked this complaint as resolved and satisfactory",
                        is_internal=False
                    )
                    
                    # Notify staff
                    if complaint.assigned_to:
                        send_complaint_notification(
                            complaint, 
                            f"Student marked complaint #{complaint.id} as resolved"
                        )
                    
                    messages.success(request, "Complaint marked as resolved. Thank you for your feedback!")
                else:
                    messages.error(request, "You can only mark complaints as resolved when they are in progress")
            
            elif action == 'escalate':
                if complaint.priority == 'CRIT':
                    messages.error(request, "This complaint is already at critical priority")
                else:
                    escalation_reason = request.POST.get('escalation_reason', '')
                    escalation_details = request.POST.get('escalation_details', '').strip()
                    
                    if escalation_reason and escalation_details:
                        # Upgrade priority
                        old_priority = complaint.priority
                        complaint.priority = 'HIGH' if complaint.priority != 'HIGH' else 'CRIT'
                        complaint.save()
                        
                        # Add escalation comment
                        reason_map = {
                            'no_response': 'No response from assigned staff',
                            'delayed_resolution': 'Resolution is taking too long',
                            'unsatisfactory_response': 'Unsatisfactory response from staff',
                            'urgent_issue': 'Issue has become more urgent',
                            'other': 'Other'
                        }
                        
                        Comment.objects.create(
                            complaint=complaint,
                            author=None,  # Student comment
                            content=f"ESCALATED by student\nReason: {reason_map.get(escalation_reason, escalation_reason)}\n\nDetails: {escalation_details}",
                            is_internal=False
                        )
                        
                        # Add VC and Registrar as trackers for escalated complaints
                        vc = Staff.objects.filter(role='VC').first()
                        reg = Staff.objects.filter(role='REG').first()
                        if vc:
                            complaint.trackers.add(vc)
                        if reg:
                            complaint.trackers.add(reg)
                        
                        # Send notifications
                        send_complaint_notification(
                            complaint, 
                            f"Complaint #{complaint.id} has been ESCALATED by student - Priority upgraded to {complaint.get_priority_display()}"
                        )
                        
                        messages.warning(request, 
                            f"Complaint escalated successfully. Priority upgraded to {complaint.get_priority_display()}. "
                            f"Senior management has been notified."
                        )
                    else:
                        messages.error(request, "Please provide both reason and details for escalation")
            
            return redirect('complaint_detail', complaint_id=complaint.id)
        # ==================== END OF NEW STUDENT ACTION HANDLING CODE ====================

    else:
        comment_form = CommentForm()
        status_form = StatusUpdateForm(initial={'status': complaint.status})

    # Get comments (filter internal comments for students)
    comments = Comment.objects.filter(complaint=complaint).order_by('created_at')
    if is_student:
        comments = comments.filter(is_internal=False)

    # Get tracking information
    tracking_info = {
        'assigned_to': complaint.assigned_to,
        'trackers': complaint.trackers.all(),
        'can_track': is_tracker or is_assigned_staff,
        'can_update_status': is_assigned_staff,
        'can_comment': is_staff,
    }

    context = {
        'complaint': complaint,
        'comments': comments,
        'comment_form': comment_form,
        'status_form': status_form,
        'is_staff': is_staff,
        'is_student': is_student,
        'is_assigned_staff': is_assigned_staff,
        'is_tracker': is_tracker,
        'is_hod': is_hod,
        'tracking_info': tracking_info,
    }
    return render(request, 'complaint_detail.html', context)

def send_complaint_notification(complaint, message):
    """Send notifications via WebSockets (placeholder for implementation)"""
    # This would integrate with your WebSocket setup
    # channel_layer = get_channel_layer()
    # group_name = f'complaint_{complaint.id}'
    # async_to_sync(channel_layer.group_send)(
    #     group_name,
    #     {
    #         'type': 'complaint_update',
    #         'message': message,
    #         'complaint_id': complaint.id,
    #     }
    # )
    pass

@login_required
def staff_dashboard(request):
    """Enhanced dashboard for staff with improved filtering and tracking"""
    try:
        staff = request.user.staff
    except Staff.DoesNotExist:
        messages.error(request, "You need a staff account to access this page.")
        return redirect('login')

    # Base queryset: complaints assigned to or tracked by this staff member
    base_complaints = Complaint.objects.filter(
        Q(assigned_to=staff) | Q(trackers=staff)
    ).distinct()

    # Special rules for HODs - they can see all complaints from their department students
    # AND complaints assigned to them (which includes academic complaints)
    if staff.role == 'HOD' and staff.department:
        department_complaints = Complaint.objects.filter(
            student__department=staff.department
        ).distinct()
        # This union ensures HODs see both tracked complaints AND department complaints
        base_complaints = (base_complaints | department_complaints).distinct()

    # Apply filters
    filtered_complaints = base_complaints
    
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    category_filter = request.GET.get('category')
    assignment_filter = request.GET.get('assignment')
    
    if status_filter:
        filtered_complaints = filtered_complaints.filter(status=status_filter)
    if priority_filter:
        filtered_complaints = filtered_complaints.filter(priority=priority_filter)
    if category_filter:
        filtered_complaints = filtered_complaints.filter(category=category_filter)
    if assignment_filter == 'assigned_to_me':
        filtered_complaints = filtered_complaints.filter(assigned_to=staff)
    elif assignment_filter == 'tracking':
        filtered_complaints = filtered_complaints.filter(trackers=staff)

    # Order complaints by priority and creation date
    filtered_complaints = filtered_complaints.order_by('-priority', '-created_at')

    # Pagination
    paginator = Paginator(filtered_complaints, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics for dashboard - Fixed to include assigned complaints
    stats = {
        'total_assigned': base_complaints.filter(assigned_to=staff).count(),
        'total_tracking': base_complaints.filter(trackers=staff).count(),
        'total_department': base_complaints.filter(student__department=staff.department).count() if staff.role == 'HOD' and staff.department else 0,
        'pending_count': base_complaints.filter(status='PEND').count(),
        'in_progress_count': base_complaints.filter(status__in=['REVW', 'ASSG', 'PROG']).count(),
        'critical_count': base_complaints.filter(priority='CRIT').count(),
        'high_priority_count': base_complaints.filter(priority='HIGH').count(),
        'academic_complaints': base_complaints.filter(category='ACAD').count() if staff.role == 'HOD' else 0,
    }

    context = {
        'staff': staff,
        'page_obj': page_obj,
        'stats': stats,
        'is_staff': True,
        'is_hod': (staff.role == 'HOD'),
        'is_wd': (staff.role == 'WD'),
        'is_sa': (staff.role == 'SA'),
        'is_hw': (staff.role == 'HW'),
        'is_vc': (staff.role == 'VC'),
        'is_reg': (staff.role == 'REG'),
    }
    return render(request, 'staff_dashboard.html', context)


@login_required
def works_dashboard(request):
    """Dashboard for Works Department staff to view infrastructure complaints."""
    try:
        staff = request.user.staff
        if staff.role != 'WD':
            messages.error(request, "You do not have permission to access the Works Department dashboard.")
            return redirect('dashboard')
    except Staff.DoesNotExist:
        messages.error(request, "You need a staff account to access this page.")
        return redirect('login')

    # Base queryset for infrastructure complaints assigned to or tracked by WD staff
    # Using Q objects to combine conditions for assigned or tracked complaints
    complaints_queryset = Complaint.objects.filter(
        Q(category='INFRA'),
        Q(assigned_to=staff) | Q(trackers=staff)
    ).distinct().order_by('-priority', '-created_at')


    # Apply filters from request.GET
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    location_type_filter = request.GET.get('location_type')

    if status_filter:
        complaints_queryset = complaints_queryset.filter(status=status_filter)
    if priority_filter:
        complaints_queryset = complaints_queryset.filter(priority=priority_filter)
    if location_type_filter:
        complaints_queryset = complaints_queryset.filter(location_type=location_type_filter)

    # Pagination
    paginator = Paginator(complaints_queryset, 10)  # Show 10 complaints per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate statistics for Works Department dashboard (infrastructure complaints)
    base_infra_complaints = Complaint.objects.filter(
        Q(category='INFRA'),
        Q(assigned_to=staff) | Q(trackers=staff)
    ).distinct()

    stats = {
        'total_assigned_infra': base_infra_complaints.count(),
        'pending_infra': base_infra_complaints.filter(status='PEND').count(),
        'in_progress_infra': base_infra_complaints.filter(status__in=['REVW', 'ASSG', 'PROG']).count(),
        'resolved_infra': base_infra_complaints.filter(status='RESV').count(),
        'critical_infra': base_infra_complaints.filter(priority='CRIT').count(),
        'high_priority_infra': base_infra_complaints.filter(priority='HIGH').count(),
        'hostel_infra': base_infra_complaints.filter(location_type='HOSTEL').count(),
        'lecture_infra': base_infra_complaints.filter(location_type='LECTURE').count(),
        # Add more specific stats if needed
    }

    context = {
        'staff': staff,
        'page_obj': page_obj,
        'stats': stats,
    }
    return render(request, 'works_dashboard.html', context)

# Authentication Views
@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome, {user.get_full_name() or user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    user_name = request.user.get_full_name() or request.user.username
    logout(request)
    messages.info(request, f"Goodbye {user_name}! You have been logged out.")
    return redirect('login')

def account_type_selection(request):
    """View for selecting account type during registration"""
    return render(request, 'accounts/account_type_selection.html')

def register_student_view(request):
    """Registration view for students with enhanced validation"""
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 
                f"Student account created successfully for {user.get_full_name()}! "
                f"You can now log in with username: {user.username}"
            )
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'accounts/register_student.html', {'form': form})

def register_staff_view(request):
    """Registration view for staff with enhanced validation"""
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            staff_role = user.staff.get_role_display()
            messages.success(request, 
                f"Staff account created successfully for {user.get_full_name()} "
                f"as {staff_role}! You can now log in with username: {user.username}"
            )
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        form = StaffRegistrationForm()
    
    return render(request, 'accounts/register_staff.html', {'form': form})

@login_required
def complaint_tracking_view(request, complaint_id):
    """Special view for tracking complaint progress - available to all authorized users"""
    complaint = get_object_or_404(Complaint, pk=complaint_id)
    
    if not complaint.can_user_view(request.user):
        messages.error(request, "You don't have permission to track this complaint")
        return redirect('dashboard')
    
    # Get all updates and comments in chronological order
    updates = []
    
    # Add status changes from comments
    status_comments = Comment.objects.filter(
        complaint=complaint,
        content__icontains='Status changed'
    ).order_by('created_at')
    
    for comment in status_comments:
        updates.append({
            'type': 'status_change',
            'timestamp': comment.created_at,
            'content': comment.content,
            'author': comment.author,
        })
    
    # Add regular comments
    regular_comments = Comment.objects.filter(
        complaint=complaint,
        is_internal=False
    ).exclude(content__icontains='Status changed').order_by('created_at')
    
    for comment in regular_comments:
        updates.append({
            'type': 'comment',
            'timestamp': comment.created_at,
            'content': comment.content,
            'author': comment.author,
        })
    
    # Sort all updates by timestamp
    updates.sort(key=lambda x: x['timestamp'])
    
    context = {
        'complaint': complaint,
        'updates': updates,
        'tracking_staff': complaint.trackers.all(),
        'assigned_staff': complaint.assigned_to,
    }
    
    return render(request, 'complaint_tracking.html', context)