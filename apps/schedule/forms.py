from django import forms
from .models import Schedule, Attendance, LeaveRequest
from apps.accounts.models import Employee
from apps.customers.models import Area


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['employee', 'date', 'shift', 'assigned_area', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(
            is_active=True
        ).select_related('user', 'role')
        self.fields['assigned_area'].queryset = Area.objects.filter(is_active=True)
        self.fields['assigned_area'].required = False


class BulkScheduleForm(forms.Form):
    """Assign same shift to multiple employees for a date"""
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    shift = forms.ChoiceField(choices=Schedule.SHIFT_CHOICES)
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_active=True).select_related('user'),
        widget=forms.CheckboxSelectMultiple
    )
    assigned_area = forms.ModelChoiceField(
        queryset=Area.objects.filter(is_active=True),
        required=False
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'status', 'check_in', 'check_out', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in': forms.TimeInput(attrs={'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(
            is_active=True
        ).select_related('user', 'role')


class BulkAttendanceForm(forms.Form):
    """Mark attendance for multiple employees at once"""
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(
            is_active=True
        ).select_related('user', 'role')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('End date must be after start date.')
        return cleaned_data


class LeaveApprovalForm(forms.Form):
    status = forms.ChoiceField(choices=[
        ('approved', 'Approve'),
        ('rejected', 'Reject'),
    ])
    approval_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Notes'
    )