# models.py
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return self.name

class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ROLE_CHOICES = [
        ('VC', 'Vice Chancellor'),
        ('REG', 'Registrar'),
        ('SA', 'Student Affairs'),
        ('SEC', 'Security Officer'),
        ('HW', 'Hall Warden'),
        ('WD', 'Works Department'),
        ('HOD', 'Head of Department'),
    ]
    role = models.CharField(max_length=3, choices=ROLE_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    can_track = models.ManyToManyField('self', symmetrical=False, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    hostel = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

class Complaint(models.Model):
    CATEGORY_CHOICES = [
        ('INFRA', 'Infrastructure'),
        ('HOSTEL', 'Hostel'),
        ('SAFETY', 'Safety'),
        ('HARASS', 'Harassment'),
        ('ACAD', 'Academic'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MED', 'Medium'),
        ('HIGH', 'High'),
        ('CRIT', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('PEND', 'Pending'),
        ('REVW', 'Under Review'),
        ('ASSG', 'Assigned'),
        ('PROG', 'In Progress'),
        ('RESV', 'Resolved'),
        ('CLSD', 'Closed'),
    ]
    
    LOCATION_CHOICES = [
        ('LECTURE', 'Lecture Room'),
        ('LAB', 'Laboratory'),
        ('LIBRARY', 'Library'),
        ('HOSTEL', 'Hostel'),
        ('CAFETERIA', 'Cafeteria'),
        ('SPORTS', 'Sports Facility'),
        ('ADMIN', 'Administrative Building'),
        ('OTHER', 'Other'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True, null=True)
    location_type = models.CharField(max_length=10, choices=LOCATION_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    category = models.CharField(max_length=6, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=4, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=4, choices=STATUS_CHOICES, default='PEND')
    
    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='assigned_complaints')
    trackers = models.ManyToManyField(Staff, related_name='tracked_complaints', blank=True)
    
    sentiment_score = models.FloatField(default=0.0)
    is_confidential = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = _('Complaint')
        verbose_name_plural = _('Complaints')
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_absolute_url(self):
        return reverse('complaint_detail', args=[str(self.id)])
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self._assign_complaint()
            self._assign_trackers()
    
    def _assign_complaint(self):
        """Enhanced assignment logic based on category and location"""
        assigned_staff = None
        
        # Infrastructure complaints
        if self.category == 'INFRA':
            # All infrastructure issues go to Works Department
            assigned_staff = Staff.objects.filter(role='WD').first()
        
        # Hostel complaints
        elif self.category == 'HOSTEL':
            # All hostel issues go to Hall Warden
            assigned_staff = Staff.objects.filter(role='HW').first()
        
        # Safety complaints
        elif self.category == 'SAFETY':
            # Safety issues go to Student Affairs
            assigned_staff = Staff.objects.filter(role='SA').first()
        
        # Harassment complaints
        elif self.category == 'HARASS':
            # Harassment issues go to Student Affairs
            assigned_staff = Staff.objects.filter(role='SA').first()
        
        # Academic complaints
        elif self.category == 'ACAD':
            # Academic issues go to student's HOD
            assigned_staff = Staff.objects.filter(
                role='HOD', 
                department=self.student.department
            ).first()
        
        if assigned_staff:
            self.assigned_to = assigned_staff
            self.status = 'ASSG'
            self.save(update_fields=['assigned_to', 'status'])
    
    def _assign_trackers(self):
        """Enhanced tracking logic based on complaint type and context"""
        trackers_to_add = []
        
        # Critical complaints are always tracked by VC and Registrar
        if self.priority in ['HIGH', 'CRIT']:
            vc = Staff.objects.filter(role='VC').first()
            reg = Staff.objects.filter(role='REG').first()
            if vc:
                trackers_to_add.append(vc)
            if reg:
                trackers_to_add.append(reg)
        
        # Infrastructure complaints in hostel - both Works Dept and Hall Warden track
        if self.category == 'INFRA' and (
            self.location_type == 'HOSTEL' or 
            (self.location and 'hostel' in self.location.lower())
        ):
            hw = Staff.objects.filter(role='HW').first()
            if hw:
                trackers_to_add.append(hw)
        
        # Infrastructure complaints in lecture rooms - HOD tracks
        elif self.category == 'INFRA' and (
            self.location_type in ['LECTURE', 'LAB'] or
            (self.location and any(term in self.location.lower() 
                                 for term in ['lecture', 'classroom', 'lab']))
        ):
            hod = Staff.objects.filter(
                role='HOD', 
                department=self.student.department
            ).first()
            if hod:
                trackers_to_add.append(hod)
        
        # Harassment/Safety complaints - student's HOD tracks
        elif self.category in ['HARASS', 'SAFETY']:
            hod = Staff.objects.filter(
                role='HOD', 
                department=self.student.department
            ).first()
            if hod:
                trackers_to_add.append(hod)
        
        # Academic complaints - only student's HOD handles and tracks
        elif self.category == 'ACAD':
            hod = Staff.objects.filter(
                role='HOD', 
                department=self.student.department
            ).first()
            if hod:
                trackers_to_add.append(hod)
        
        # Hostel complaints - student's HOD also tracks
        elif self.category == 'HOSTEL':
            hod = Staff.objects.filter(
                role='HOD', 
                department=self.student.department
            ).first()
            if hod:
                trackers_to_add.append(hod)
        
        # Add all trackers
        for tracker in trackers_to_add:
            self.trackers.add(tracker)
    
    def get_all_authorized_viewers(self):
        """Get all users who can view this complaint"""
        authorized_users = []
        
        # Student who created the complaint
        authorized_users.append(self.student.user)
        
        # Assigned staff
        if self.assigned_to:
            authorized_users.append(self.assigned_to.user)
        
        # All trackers
        for tracker in self.trackers.all():
            authorized_users.append(tracker.user)
        
        return authorized_users
    
    def can_user_view(self, user):
        """Check if a user can view this complaint"""
        # Student who created the complaint
        try:
            if user.student == self.student:
                return True
        except:
            pass
        
        # Staff members
        try:
            staff = user.staff
            # Assigned staff
            if staff == self.assigned_to:
                return True
            # Trackers
            if staff in self.trackers.all():
                return True
            # HODs can view complaints from their department students
            if (staff.role == 'HOD' and 
                staff.department == self.student.department):
                return True
        except:
            pass
        
        return False

class Comment(models.Model):
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Staff, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_internal = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
    
    def __str__(self):
        return f"Comment by {self.author} on {self.complaint}"