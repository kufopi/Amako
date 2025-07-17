# forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Complaint, Comment, Student, Staff, Department

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['title', 'description', 'location', 'location_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief title of your complaint'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe your complaint in detail',
                'rows': 5
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Specific location (e.g., Room 101, Block A)'
            }),
            'location_type': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'location_type': 'Location Type',
            'location': 'Specific Location (Optional)'
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content', 'is_internal']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your comment or update'
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'is_internal': 'Internal note (not visible to student)'
        }

class StatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }

class StudentRegistrationForm(UserCreationForm):
    """Form for student registration"""
    student_id = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Required. 20 characters or fewer.'
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select your department",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select your department'
    )
    hostel = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Optional. Enter your hostel name if applicable.'
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Required. Enter a valid email address.'
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Required.'
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Required.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            Student.objects.create(
                user=user,
                student_id=self.cleaned_data['student_id'],
                department=self.cleaned_data['department'],
                hostel=self.cleaned_data.get('hostel', '')
            )
        return user

class StaffRegistrationForm(UserCreationForm):
    """Form for staff registration with department field for HODs"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Required. Enter a valid email address.'
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Required.'
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Required.'
    )
    role = forms.ChoiceField(
        choices=Staff.ROLE_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select your role'
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select your department (if HOD)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Required for HODs. Select your department.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        department = cleaned_data.get('department')

        if role == 'HOD' and not department:
            self.add_error('department', 'Department is required for HODs')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            Staff.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                department=self.cleaned_data.get('department')
            )
        return user