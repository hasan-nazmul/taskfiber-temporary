from django import forms
from django.contrib.auth.models import User
from .models import Employee, Role, Team

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description', 'leader', 'members']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'members': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input flex-shrink-0 me-2'}),
        }


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=15,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your phone number',
            'type': 'tel',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Password'
        })
    )


class EmployeeUserForm(forms.ModelForm):
    """Form for the User part of Employee"""
    def __init__(self, *args, **kwargs):
        has_full_perms = kwargs.pop('has_full_perms', True)
        can_grant_manager = kwargs.pop('can_grant_manager', True) # Handle pop but logic may be same
        super().__init__(*args, **kwargs)
        if not has_full_perms:
            if 'username' in self.fields:
                self.fields['username'].disabled = True

    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField(required=False)
    username = forms.CharField(max_length=150)
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text='Leave blank to keep current password (on edit)'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']


class EmployeeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        has_full_perms = kwargs.pop('has_full_perms', True)
        can_grant_manager = kwargs.pop('can_grant_manager', True)
        super().__init__(*args, **kwargs)
        
        # If user doesn't have permissions, they cannot grant/edit Manager/Owner roles
        if 'role' in self.fields and not can_grant_manager:
            qs = Role.objects.exclude(slug__in=['owner', 'manager'])
            if self.instance and hasattr(self.instance, 'role') and self.instance.role:
                qs = qs | Role.objects.filter(pk=self.instance.role.pk)
            self.fields['role'].queryset = qs
            
        if not has_full_perms:
            restricted_fields = [
                'employee_id', 'department',
                'date_joined_company', 'salary', 'is_active', 'notes',
            ]
            for field in restricted_fields:
                if field in self.fields:
                    self.fields[field].disabled = True

    class Meta:
        model = Employee
        fields = [
            'employee_id', 'role', 'phone', 'whatsapp_number',
            'nid_number', 'address', 'department',
            'date_joined_company', 'salary', 'is_active',
            'assigned_area', 'profile_photo', 'notes',
            'telegram_chat_id',
        ]
        widgets = {
            'date_joined_company': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ModuleAccessForm(forms.ModelForm):
    class Meta:
        from .models import ModuleAccess
        model = ModuleAccess
        fields = [
            'tickets_access', 'customers_access', 'zones_access', 'stock_access',
            'schedule_access', 'employees_access', 'teams_access', 'accounts_finance_access'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-select')
        widgets = {
            'tickets_access': forms.Select(attrs={'class': 'form-select'}),
            'customers_access': forms.Select(attrs={'class': 'form-select'}),
            'stock_access': forms.Select(attrs={'class': 'form-select'}),
            'schedule_access': forms.Select(attrs={'class': 'form-select'}),
            'employees_access': forms.Select(attrs={'class': 'form-select'}),
            'teams_access': forms.Select(attrs={'class': 'form-select'}),
            'accounts_finance_access': forms.Select(attrs={'class': 'form-select'}),
        }