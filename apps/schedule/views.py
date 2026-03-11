from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from datetime import timedelta, date

from .models import Schedule, Attendance, LeaveRequest
from .forms import (
    ScheduleForm, BulkScheduleForm,
    AttendanceForm, BulkAttendanceForm,
    LeaveRequestForm, LeaveApprovalForm
)
from apps.accounts.models import Employee
from apps.accounts.decorators import check_module_access


def get_employee(request):
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


def get_week_dates(target_date=None):
    """Get list of dates for the week containing target_date (Monday-Sunday)"""
    if target_date is None:
        target_date = timezone.now().date()
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)

    # Find Monday of the week
    monday = target_date - timedelta(days=target_date.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


@login_required
@check_module_access('schedule', 'view')
def schedule_view(request):
    """Weekly schedule view for all employees"""
    # Get target week
    week_start = request.GET.get('week')
    if week_start:
        try:
            target_date = date.fromisoformat(week_start)
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    week_dates = get_week_dates(target_date)
    week_start_date = week_dates[0]
    week_end_date = week_dates[-1]

    # Navigation
    prev_week = (week_start_date - timedelta(days=7)).isoformat()
    next_week = (week_start_date + timedelta(days=7)).isoformat()
    current_week = timezone.now().date().isoformat()

    # Get all active employees
    employees = Employee.objects.filter(is_active=True).select_related('user', 'role')

    # Get schedules for the week
    schedules = Schedule.objects.filter(
        date__gte=week_start_date,
        date__lte=week_end_date
    ).select_related('employee', 'assigned_area')

    # Build schedule matrix: {employee_id: {date: schedule}}
    schedule_matrix = {}
    for emp in employees:
        schedule_matrix[emp.id] = {d: None for d in week_dates}

    for sch in schedules:
        if sch.employee_id in schedule_matrix and sch.date in schedule_matrix[sch.employee_id]:
            schedule_matrix[sch.employee_id][sch.date] = sch

    # Day names for header
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    context = {
        'employees': employees,
        'week_dates': week_dates,
        'day_names': day_names,
        'schedule_matrix': schedule_matrix,
        'week_start_date': week_start_date,
        'week_end_date': week_end_date,
        'prev_week': prev_week,
        'next_week': next_week,
        'current_week': current_week,
        'today': timezone.now().date(),
    }
    return render(request, 'schedule/schedule_view.html', context)


@login_required
@check_module_access('schedule', 'edit')
def schedule_assign(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('schedule_view')

    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.created_by = employee
            try:
                schedule.save()
                messages.success(
                    request,
                    f'Schedule assigned: {schedule.employee.full_name} on {schedule.date}'
                )
                return redirect('schedule_view')
            except Exception as e:
                # Unique constraint violation - update existing
                existing = Schedule.objects.filter(
                    employee=schedule.employee, date=schedule.date
                ).first()
                if existing:
                    existing.shift = schedule.shift
                    existing.assigned_area = schedule.assigned_area
                    existing.notes = schedule.notes
                    existing.save()
                    messages.success(
                        request,
                        f'Schedule updated: {schedule.employee.full_name} on {schedule.date}'
                    )
                    return redirect('schedule_view')
                else:
                    messages.error(request, f'Error: {str(e)}')
    else:
        initial = {}
        emp_id = request.GET.get('employee')
        sched_date = request.GET.get('date')
        if emp_id:
            initial['employee'] = emp_id
        if sched_date:
            initial['date'] = sched_date
        form = ScheduleForm(initial=initial)

    return render(request, 'schedule/schedule_form.html', {
        'form': form,
        'title': 'Assign Schedule',
    })


@login_required
@check_module_access('schedule', 'edit')
def schedule_bulk_assign(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('schedule_view')

    if request.method == 'POST':
        form = BulkScheduleForm(request.POST)
        if form.is_valid():
            target_date = form.cleaned_data['date']
            shift = form.cleaned_data['shift']
            employees = form.cleaned_data['employees']
            assigned_area = form.cleaned_data.get('assigned_area')
            notes = form.cleaned_data.get('notes', '')

            created = 0
            updated = 0
            for emp in employees:
                sch, was_created = Schedule.objects.update_or_create(
                    employee=emp,
                    date=target_date,
                    defaults={
                        'shift': shift,
                        'assigned_area': assigned_area,
                        'notes': notes,
                        'created_by': employee,
                    }
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            messages.success(
                request,
                f'Bulk schedule: {created} created, {updated} updated for {target_date}'
            )
            return redirect('schedule_view')
    else:
        form = BulkScheduleForm()

    return render(request, 'schedule/schedule_bulk_form.html', {
        'form': form,
        'title': 'Bulk Schedule Assignment',
    })


@login_required
@require_POST
@check_module_access('schedule', 'full')
def schedule_delete(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    schedule.delete()
    messages.success(request, 'Schedule entry deleted.')
    return redirect('schedule_view')


# --- Attendance ---

@login_required
@check_module_access('schedule', 'edit')
def attendance_mark(request):
    """Mark attendance for all employees for a specific date"""
    employee = get_employee(request)
    target_date_str = request.GET.get('date', timezone.now().date().isoformat())

    try:
        target_date = date.fromisoformat(target_date_str)
    except ValueError:
        target_date = timezone.now().date()

    employees = Employee.objects.filter(is_active=True).select_related('user', 'role')

    # Get existing attendance for the date
    existing_attendance = {
        a.employee_id: a
        for a in Attendance.objects.filter(date=target_date)
    }

    if request.method == 'POST' and employee:
        # Process bulk attendance
        for emp in employees:
            status = request.POST.get(f'status_{emp.id}', '')
            check_in = request.POST.get(f'check_in_{emp.id}', '')
            check_out = request.POST.get(f'check_out_{emp.id}', '')
            notes = request.POST.get(f'notes_{emp.id}', '')

            if status:
                Attendance.objects.update_or_create(
                    employee=emp,
                    date=target_date,
                    defaults={
                        'status': status,
                        'check_in': check_in if check_in else None,
                        'check_out': check_out if check_out else None,
                        'notes': notes,
                        'marked_by': employee,
                    }
                )

        messages.success(request, f'Attendance marked for {target_date}')
        return redirect(f"{request.path}?date={target_date.isoformat()}")

    # Navigation
    prev_date = (target_date - timedelta(days=1)).isoformat()
    next_date = (target_date + timedelta(days=1)).isoformat()

    context = {
        'employees': employees,
        'existing_attendance': existing_attendance,
        'target_date': target_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'today': timezone.now().date().isoformat(),
        'status_choices': Attendance.STATUS_CHOICES,
    }
    return render(request, 'schedule/attendance_mark.html', context)


@login_required
@check_module_access('schedule', 'view')
def attendance_report(request):
    """Monthly attendance summary"""
    target_month = request.GET.get('month')
    if target_month:
        try:
            year, month = map(int, target_month.split('-'))
        except ValueError:
            year = timezone.now().year
            month = timezone.now().month
    else:
        year = timezone.now().year
        month = timezone.now().month

    # Get date range for the month
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    employees = Employee.objects.filter(is_active=True).select_related('user', 'role')

    # Get all attendance records for the month
    attendances = Attendance.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )

    # Build summary
    summary = {}
    for emp in employees:
        emp_attendance = attendances.filter(employee=emp)
        summary[emp.id] = {
            'employee': emp,
            'present': emp_attendance.filter(status='present').count(),
            'absent': emp_attendance.filter(status='absent').count(),
            'late': emp_attendance.filter(status='late').count(),
            'half_day': emp_attendance.filter(status='half_day').count(),
            'leave': emp_attendance.filter(status='leave').count(),
            'total_marked': emp_attendance.count(),
        }

    # Month navigation
    if month == 1:
        prev_month = f"{year - 1}-12"
    else:
        prev_month = f"{year}-{month - 1:02d}"

    if month == 12:
        next_month = f"{year + 1}-01"
    else:
        next_month = f"{year}-{month + 1:02d}"

    context = {
        'summary': summary,
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B %Y'),
        'days_in_month': days_in_month,
        'prev_month': prev_month,
        'next_month': next_month,
    }
    return render(request, 'schedule/attendance_report.html', context)


# --- Leave Requests ---

@login_required
def leave_request_list(request):
    employee = get_employee(request)
    is_hr = request.user.is_superuser or (employee and employee.is_manager)
    if not is_hr and employee:
        try:
            access = employee.module_access
            if access.schedule_access in ('edit', 'full'):
                is_hr = True
        except Exception:
            pass

    leaves = LeaveRequest.objects.select_related(
        'employee', 'employee__user', 'approved_by'
    ).all()

    # Regular employees only see their own leave requests
    if not is_hr:
        if employee:
            leaves = leaves.filter(employee=employee)
        else:
            leaves = leaves.none()

    status_filter = request.GET.get('status', '')
    if status_filter:
        leaves = leaves.filter(status=status_filter)

    context = {
        'leaves': leaves,
        'filters': {'status': status_filter},
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'is_hr': is_hr,
    }
    return render(request, 'schedule/leave_list.html', context)


@login_required
def leave_request_create(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('dashboard')

    is_admin = request.user.is_superuser or employee.is_manager

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            # Regular employees can only submit leave for themselves
            if not is_admin and leave.employee != employee:
                messages.error(request, 'You can only submit leave requests for yourself.')
                return redirect('leave_request_create')
            leave.save()
            messages.success(request, 'Leave request submitted.')
            return redirect('leave_request_list')
    else:
        initial = {'employee': employee}
        form = LeaveRequestForm(initial=initial)
        # For regular employees, lock the employee field to themselves
        if not is_admin:
            form.fields['employee'].queryset = Employee.objects.filter(pk=employee.pk)
            form.fields['employee'].disabled = True

    return render(request, 'schedule/leave_form.html', {
        'form': form,
        'title': 'Submit Leave Request',
    })


@login_required
@check_module_access('schedule', 'edit')
def leave_request_approve(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    employee = get_employee(request)

    if employee and leave.employee == employee:
        messages.error(request, 'You cannot approve or reject your own leave request.')
        return redirect('leave_request_list')

    if request.method == 'POST':
        form = LeaveApprovalForm(request.POST)
        if form.is_valid() and employee:
            leave.status = form.cleaned_data['status']
            leave.approved_by = employee
            leave.approval_notes = form.cleaned_data.get('approval_notes', '')
            leave.save()

            # If approved, mark attendance as leave for those dates
            if leave.status == 'approved':
                current_date = leave.start_date
                while current_date <= leave.end_date:
                    Attendance.objects.update_or_create(
                        employee=leave.employee,
                        date=current_date,
                        defaults={
                            'status': 'leave',
                            'notes': f'Leave: {leave.get_leave_type_display()}',
                            'marked_by': employee,
                        }
                    )
                    current_date += timedelta(days=1)

            action = 'approved' if leave.status == 'approved' else 'rejected'
            messages.success(request, f'Leave request {action}.')
            return redirect('leave_request_list')
    else:
        form = LeaveApprovalForm()

    return render(request, 'schedule/leave_approve.html', {
        'leave': leave,
        'form': form,
    })