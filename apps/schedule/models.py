from django.db import models


class Schedule(models.Model):
    SHIFT_CHOICES = [
        ('morning', 'Morning (8AM-4PM)'),
        ('evening', 'Evening (4PM-12AM)'),
        ('night', 'Night (12AM-8AM)'),
        ('full_day', 'Full Day'),
        ('off', 'Day Off'),
    ]

    employee = models.ForeignKey(
        'accounts.Employee', on_delete=models.CASCADE,
        related_name='schedules'
    )
    date = models.DateField()
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)

    assigned_area = models.ForeignKey(
        'customers.Area', null=True, blank=True,
        on_delete=models.SET_NULL
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT,
        related_name='schedules_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.get_shift_display()}"

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['date', 'employee']


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('leave', 'On Leave'),
    ]

    employee = models.ForeignKey(
        'accounts.Employee', on_delete=models.CASCADE,
        related_name='attendances'
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    marked_by = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='attendance_marked'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.get_status_display()}"

    @property
    def hours_worked(self):
        if self.check_in and self.check_out:
            from datetime import datetime, timedelta
            cin = datetime.combine(self.date, self.check_in)
            cout = datetime.combine(self.date, self.check_out)
            if cout < cin:
                cout += timedelta(days=1)
            diff = cout - cin
            return round(diff.total_seconds() / 3600, 1)
        return None

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
        indexes = [
            models.Index(fields=['date', 'status']),
        ]


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('casual', 'Casual Leave'),
        ('sick', 'Sick Leave'),
        ('emergency', 'Emergency'),
        ('annual', 'Annual Leave'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(
        'accounts.Employee', on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='leaves_approved'
    )
    approval_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"

    @property
    def total_days(self):
        return (self.end_date - self.start_date).days + 1

    class Meta:
        ordering = ['-created_at']