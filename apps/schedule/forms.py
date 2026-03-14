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
        employee = cleaned_data.get('employee')

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('End date must be after start date.')

        # Prevent past-date leave requests
        from django.utils import timezone
        today = timezone.now().date()
        if start_date and start_date < today:
            self.add_error('start_date', 'Start date cannot be in the past.')
        if end_date and end_date < today:
            self.add_error('end_date', 'End date cannot be in the past.')

        # Prevent overlapping with existing approved/pending leaves
        if employee and start_date and end_date:
            from .models import LeaveRequest
            overlapping = LeaveRequest.objects.filter(
                employee=employee,
                status__in=['approved', 'pending'],
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                leave = overlapping.first()
                raise forms.ValidationError(
                    f'This overlaps with an existing {leave.get_status_display().lower()} leave '
                    f'({leave.start_date.strftime("%b %d")} - {leave.end_date.strftime("%b %d")}).'
                )

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