from django import forms
from .models import Complaint, Comment, Student, Staff
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class ComplaintForm(forms.ModelForm):
    """Form for students to submit complaints"""
    
    class Meta:
        model = Complaint
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a brief title for your complaint'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Please describe your complaint in detail',
                'rows': 5
            })
        }

class CommentForm(forms.ModelForm):
    """Form for staff to add comments to complaints"""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your comment or resolution',
                'rows': 3
            })
        }

class ComplaintStatusForm(forms.ModelForm):
    """Form to update complaint status"""
    
    class Meta:
        model = Complaint
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'})
        }


class StudentRegistrationForm(UserCreationForm):
    """Form for student registration"""
    student_id = forms.CharField(
        max_length=20, 
        required=True, 
        help_text='Required. Enter your student ID.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        max_length=100, 
        required=True, 
        help_text='Required. Enter your department.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True, 
        help_text='Required. Enter a valid email address.',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30, 
        required=True, 
        help_text='Required.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True, 
        help_text='Required.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super(StudentRegistrationForm, self).__init__(*args, **kwargs)
        # Add Bootstrap classes to default form fields
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create the associated Student profile
            student = Student.objects.create(
                user=user,
                student_id=self.cleaned_data['student_id'],
                department=self.cleaned_data['department']
            )
            
        return user

class StaffRegistrationForm(UserCreationForm):
    """Form for staff registration"""
    email = forms.EmailField(
        required=True, 
        help_text='Required. Enter a valid email address.',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        max_length=30, 
        required=True, 
        help_text='Required.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True, 
        help_text='Required.',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=Staff.ROLE_CHOICES, 
        required=True, 
        help_text='Required. Select your role.',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super(StaffRegistrationForm, self).__init__(*args, **kwargs)
        # Add Bootstrap classes to default form fields
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create the associated Staff profile
            staff = Staff.objects.create(
                user=user,
                role=self.cleaned_data['role']
            )
            
        return user