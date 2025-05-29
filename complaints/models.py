from django.db import models
from django.contrib.auth.models import User

class Staff(models.Model):
    """Staff model extending Django User model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ROLE_CHOICES = [
        ('VC', 'Vice Chancellor'),
        ('REG', 'Registrar'),
        ('SA', 'Student Affairs'),
        ('SEC', 'Security Officer'),
        ('HW', 'Hall Warden'),
        ('WD', 'Works Department'),
    ]
    role = models.CharField(max_length=3, choices=ROLE_CHOICES)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"

class Student(models.Model):
    """Student model extending Django User model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

class Complaint(models.Model):
    """Model for student complaints"""
    CATEGORY_CHOICES = [
        ('MAIN', 'Maintenance Issues'),
        ('SAFE', 'Safety Issues'),
        ('CLASS', 'Lecture/Classroom Issues'),
        ('MISD', 'Misdemeanor Issues'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('MED', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRIT', 'Critical/Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('PEND', 'Pending'),
        ('REVW', 'Under Review'),
        ('ASSG', 'Assigned'),
        ('RESV', 'Resolved'),
        ('CLSD', 'Closed'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='complaints')
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Fields to be filled by sentiment analysis
    category = models.CharField(max_length=5, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=4, choices=PRIORITY_CHOICES)
    sentiment_score = models.FloatField(default=0.0)
    
    # Status tracking
    status = models.CharField(max_length=4, choices=STATUS_CHOICES, default='PEND')
    assigned_to = models.ManyToManyField(Staff, related_name='assigned_complaints', blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.get_priority_display()} ({self.get_status_display()})"
    
    def is_critical(self):
        return self.priority == 'CRIT'

class Comment(models.Model):
    """Model for staff comments on complaints"""
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='comments')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.staff.user.get_full_name()} on {self.complaint.title}"