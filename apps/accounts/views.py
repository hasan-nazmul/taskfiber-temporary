import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.db import models
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from .models import Employee, Role, ModuleAccess, Team
from .forms import LoginForm, EmployeeUserForm, EmployeeForm, ModuleAccessForm, TeamForm
from .decorators import check_module_access
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

logger = logging.getLogger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300  # 5 minutes


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Brute-force protection
    attempts = request.session.get('login_attempts', 0)
    lockout_until = request.session.get('login_lockout_until')

    if lockout_until:
        lockout_time = timezone.datetime.fromisoformat(lockout_until)
        if timezone.now() < lockout_time:
            remaining = int((lockout_time - timezone.now()).total_seconds())
            messages.error(request, f'Too many failed attempts. Try again in {remaining // 60} min {remaining % 60} sec.')
            return render(request, 'accounts/login.html', {'form': LoginForm()})
        else:
            # Lockout expired, reset
            request.session['login_attempts'] = 0
            request.session.pop('login_lockout_until', None)
            attempts = 0

    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                # Reset attempt counter on success
                request.session.pop('login_attempts', None)
                request.session.pop('login_lockout_until', None)
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')

                # Validate next URL to prevent open redirect
                next_url = request.GET.get('next', 'dashboard')
                if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    next_url = 'dashboard'
                return redirect(next_url)
            else:
                attempts += 1
                request.session['login_attempts'] = attempts
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    lockout_until = timezone.now() + timezone.timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
                    request.session['login_lockout_until'] = lockout_until.isoformat()
                    logger.warning(f'Login lockout triggered for IP: {request.META.get("REMOTE_ADDR")}')
                    messages.error(request, 'Too many failed attempts. Account locked for 5 minutes.')
                else:
                    remaining = MAX_LOGIN_ATTEMPTS - attempts
                    messages.error(request, f'Invalid phone number or password. {remaining} attempt(s) remaining.')

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


def forgot_password(request):
    """
    Renders a page instructing the user to contact their administrator
    since password reset via email/SMS is not built-in for the ISP employee structure.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    return render(request, 'accounts/forgot_password.html')


@login_required
def dashboard(request):
    from apps.tickets.models import Ticket
    from apps.stock.models import StockItem
    from django.core.cache import cache

    today = timezone.now().date()

    # Ticket stats - single aggregated query instead of 6 separate ones
    cache_key = f'dashboard_ticket_stats_{today.isoformat()}'
    ticket_stats = cache.get(cache_key)
    if not ticket_stats:
        ticket_stats = Ticket.objects.aggregate(
            open=Count('id', filter=Q(status='open')),
            assigned=Count('id', filter=Q(status='assigned')),
            in_progress=Count('id', filter=Q(status='in_progress')),
            resolved_today=Count('id', filter=Q(status='resolved', resolved_at__date=today)),
            new_today=Count('id', filter=Q(created_at__date=today)),
            total_open=Count('id', filter=~Q(status__in=['resolved', 'closed', 'cancelled'])),
            line_release_tasks=Count('id', filter=Q(ticket_type='line_release') & ~Q(status__in=['resolved', 'closed', 'cancelled'])),
            cable_team_tasks=Count('id', filter=Q(ticket_type__in=['line_cut', 'olt_down', 'mikrotik_down', 'line_shift', 'new_connection', 'db_issue', 'pon_fluctuation', 'adapter_issue']) & ~Q(status__in=['resolved', 'closed', 'cancelled'])),
            support_tasks=Count('id', filter=~Q(ticket_type__in=['line_cut', 'olt_down', 'mikrotik_down', 'line_shift', 'new_connection', 'db_issue', 'pon_fluctuation', 'adapter_issue']) & ~Q(status__in=['resolved', 'closed', 'cancelled'])),
        )
        cache.set(cache_key, ticket_stats, 60)

    # Recent tickets
    recent_tickets = Ticket.objects.select_related(
        'customer', 'assigned_to', 'created_by'
    ).order_by('-created_at')[:10]

    # My tickets (if employee)
    my_tickets = []
    if hasattr(request.user, 'employee'):
        my_tickets = Ticket.objects.filter(
            assigned_to=request.user.employee
        ).exclude(
            status__in=['resolved', 'closed', 'cancelled']
        ).order_by('-created_at')[:5]

    # Low stock alerts
    low_stock_items = StockItem.objects.filter(
        is_active=True,
        quantity_in_stock__lte=models.F('minimum_stock_level')
    )[:5]

    # Unassigned tickets
    unassigned_tickets = Ticket.objects.filter(
        assigned_to__isnull=True
    ).exclude(
        status__in=['resolved', 'closed', 'cancelled']
    ).order_by('-created_at')[:5]

    context = {
        'ticket_stats': ticket_stats,
        'recent_tickets': recent_tickets,
        'my_tickets': my_tickets,
        'low_stock_items': low_stock_items,
        'unassigned_tickets': unassigned_tickets,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile(request):
    employee = getattr(request.user, 'employee', None)
    return render(request, 'accounts/profile.html', {'employee': employee})


@login_required
def change_password(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password', '')
        new2 = request.POST.get('confirm_password', '')

        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
        elif len(new1) < 6:
            messages.error(request, 'New password must be at least 6 characters.')
        elif new1 != new2:
            messages.error(request, 'New passwords do not match.')
        elif current == new1:
            messages.error(request, 'New password must be different from current password.')
        else:
            request.user.set_password(new1)
            request.user.save()
            # Re-authenticate so the user stays logged in
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('profile')

    return render(request, 'accounts/change_password.html')


@login_required
@check_module_access('employees', 'view')
def employee_list(request):
    employees = Employee.objects.select_related('user', 'role').all()

    # Filters
    department = request.GET.get('department')
    role = request.GET.get('role')
    status = request.GET.get('status')
    search = request.GET.get('search')

    if department:
        employees = employees.filter(department=department)
    if role:
        employees = employees.filter(role__slug=role)
    if status:
        if status == 'active':
            employees = employees.filter(is_active=True)
        elif status == 'inactive':
            employees = employees.filter(is_active=False)
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(employee_id__icontains=search) |
            Q(phone__icontains=search)
        )

    roles = Role.objects.all()

    # Pagination
    paginator = Paginator(employees, 30)
    page = request.GET.get('page')
    try:
        employees_page = paginator.page(page)
    except PageNotAnInteger:
        employees_page = paginator.page(1)
    except EmptyPage:
        employees_page = paginator.page(paginator.num_pages)

    context = {
        'employees': employees_page,
        'roles': roles,
        'filters': {
            'department': department,
            'role': role,
            'status': status,
            'search': search,
        }
    }
    return render(request, 'accounts/employee_list.html', context)


def _get_filtered_employees(request):
    """Shared filter logic for employee list and export."""
    employees = Employee.objects.select_related('user', 'role').all()
    department = request.GET.get('department')
    role = request.GET.get('role')
    status = request.GET.get('status')
    search = request.GET.get('search')
    if department:
        employees = employees.filter(department=department)
    if role:
        employees = employees.filter(role__slug=role)
    if status:
        if status == 'active':
            employees = employees.filter(is_active=True)
        elif status == 'inactive':
            employees = employees.filter(is_active=False)
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search) |
            Q(employee_id__icontains=search) | Q(phone__icontains=search)
        )
    return employees


@login_required
@check_module_access('employees', 'view')
def employee_export_csv(request):
    from utils.export_helpers import csv_response
    employees = _get_filtered_employees(request)
    headers = ['Employee ID', 'Name', 'Role', 'Department', 'Phone', 'Joined', 'Status']
    rows = [
        [e.employee_id, e.full_name, e.role.name, e.get_department_display(),
         e.phone, e.date_joined_company.strftime('%Y-%m-%d') if e.date_joined_company else '',
         'Active' if e.is_active else 'Inactive']
        for e in employees
    ]
    return csv_response('employees.csv', headers, rows)


@login_required
@check_module_access('employees', 'view')
def employee_export_pdf(request):
    from utils.export_helpers import pdf_response
    employees = _get_filtered_employees(request)
    headers = ['Employee ID', 'Name', 'Role', 'Department', 'Phone', 'Joined', 'Status']
    rows = [
        [e.employee_id, e.full_name, e.role.name, e.get_department_display(),
         e.phone, e.date_joined_company.strftime('%Y-%m-%d') if e.date_joined_company else '',
         'Active' if e.is_active else 'Inactive']
        for e in employees
    ]
    return pdf_response('employees.pdf', 'Employee Report', headers, rows)


EMPLOYEE_IMPORT_HEADERS = ['First Name', 'Last Name', 'Employee ID', 'Role', 'Phone', 'Department', 'Date Joined', 'Salary']


@login_required
@check_module_access('employees', 'edit')
def employee_import_template(request):
    from utils.import_helpers import sample_csv_response
    return sample_csv_response('employee_import_template.csv', EMPLOYEE_IMPORT_HEADERS)


@login_required
@check_module_access('employees', 'edit')
def employee_import_csv(request):
    from utils.import_helpers import parse_csv
    from django.db import transaction
    from datetime import date as dt_date

    context = {
        'module_name': 'Employees',
        'back_url': '/employees/',
        'template_url': '/employees/import/template/',
        'expected_columns': EMPLOYEE_IMPORT_HEADERS,
    }

    valid_departments = ['management', 'marketing', 'support', 'technical', 'accounts']

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return render(request, 'common/csv_import.html', context)

        headers, rows = parse_csv(csv_file)
        created = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows, start=2):
            try:
                first_name = row.get('First Name', '').strip()
                last_name = row.get('Last Name', '').strip()
                if not first_name:
                    errors.append({'row': i, 'message': 'First Name is required'})
                    continue

                employee_id = row.get('Employee ID', '').strip()
                if employee_id and Employee.objects.filter(employee_id=employee_id).exists():
                    skipped += 1
                    continue

                phone = row.get('Phone', '').strip()
                if not phone:
                    errors.append({'row': i, 'message': 'Phone is required'})
                    continue
                if Employee.objects.filter(phone=phone).exists():
                    skipped += 1
                    continue

                role_name = row.get('Role', '').strip()
                if not role_name:
                    errors.append({'row': i, 'message': 'Role is required'})
                    continue
                try:
                    role = Role.objects.get(name__iexact=role_name)
                except Role.DoesNotExist:
                    errors.append({'row': i, 'message': f'Role "{role_name}" not found'})
                    continue

                department = row.get('Department', '').strip().lower()
                if department not in valid_departments:
                    errors.append({'row': i, 'message': f'Invalid department "{row.get("Department", "")}"'})
                    continue

                date_joined = None
                date_str = row.get('Date Joined', '').strip()
                if date_str:
                    try:
                        date_joined = dt_date.fromisoformat(date_str)
                    except ValueError:
                        errors.append({'row': i, 'message': f'Invalid date format "{date_str}". Use YYYY-MM-DD'})
                        continue

                salary = row.get('Salary', '0').strip() or '0'

                with transaction.atomic():
                    username = phone
                    if User.objects.filter(username=username).exists():
                        skipped += 1
                        continue

                    user = User.objects.create_user(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        password='changeme123',
                    )
                    Employee.objects.create(
                        user=user,
                        employee_id=employee_id or '',
                        role=role,
                        phone=phone,
                        department=department,
                        date_joined_company=date_joined,
                        salary=salary,
                    )
                    created += 1
            except Exception as e:
                errors.append({'row': i, 'message': str(e)})

        context['results'] = {'created': created, 'skipped': skipped, 'errors': errors}

    return render(request, 'common/csv_import.html', context)


@login_required
@check_module_access('employees', 'edit')
def employee_create(request):
    has_full_perms = False
    can_grant_manager = False
    if hasattr(request, 'user'):
        if request.user.is_superuser:
            has_full_perms = True
            can_grant_manager = True
        elif hasattr(request.user, 'employee'):
            if request.user.employee.role.slug == 'owner':
                has_full_perms = True
                can_grant_manager = True
            elif request.user.employee.is_manager:
                has_full_perms = True
            else:
                try:
                    access = request.user.employee.module_access
                    if access.employees_access in ['edit', 'full']:
                        has_full_perms = True
                except Exception:
                    pass

    if request.method == 'POST':
        user_form = EmployeeUserForm(request.POST, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)
        emp_form = EmployeeForm(request.POST, request.FILES, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)

        if user_form.is_valid() and emp_form.is_valid():
            # Create user
            user = User.objects.create_user(
                username=user_form.cleaned_data['username'],
                password=user_form.cleaned_data['password'],
                first_name=user_form.cleaned_data['first_name'],
                last_name=user_form.cleaned_data['last_name'],
                email=user_form.cleaned_data.get('email', ''),
            )

            # Create employee
            employee = emp_form.save(commit=False)
            employee.user = user
            employee.save()

            messages.success(request, f'Employee {employee.full_name} created successfully!')
            return redirect('employee_detail', pk=employee.pk)
    else:
        user_form = EmployeeUserForm(has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)
        emp_form = EmployeeForm(has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)

    return render(request, 'accounts/employee_form.html', {
        'user_form': user_form,
        'emp_form': emp_form,
        'title': 'Add New Employee',
    })


@login_required
def employee_detail(request, pk):
    # Allow view if own profile or has employees view access
    if hasattr(request, 'user') and hasattr(request.user, 'employee'):
        if request.user.employee.pk != pk and not request.user.employee.is_manager:
            try:
                access = request.user.employee.module_access
                if access.employees_access == 'none':
                    messages.error(request, "You don't have access to view other employee profiles.")
                    return redirect('dashboard')
            except Exception:
                messages.error(request, "You don't have access to view other employee profiles.")
                return redirect('dashboard')
    
    employee = get_object_or_404(Employee.objects.select_related('user', 'role'), pk=pk)

    # Get assigned tickets
    from apps.tickets.models import Ticket
    assigned_tickets = Ticket.objects.filter(
        assigned_to=employee
    ).order_by('-created_at')[:10]

    open_ticket_count = Ticket.objects.filter(
        assigned_to=employee
    ).exclude(status__in=['resolved', 'closed', 'cancelled']).count()

    context = {
        'employee': employee,
        'assigned_tickets': assigned_tickets,
        'open_ticket_count': open_ticket_count,
    }
    return render(request, 'accounts/employee_detail.html', context)


@login_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    user = employee.user

    is_target_owner_admin = user.is_superuser or (employee.role and employee.role.slug == 'owner')
    is_requester_owner_admin = request.user.is_superuser or (hasattr(request.user, 'employee') and request.user.employee and request.user.employee.role and request.user.employee.role.slug == 'owner')

    if is_target_owner_admin and not is_requester_owner_admin:
        messages.error(request, "You do not have permission to edit an Owner or System Admin.")
        return redirect('dashboard')

    has_full_perms = False
    can_grant_manager = False
    has_view_access = False
    
    # Evaluate permissions based on user role
    if hasattr(request, 'user'):
        if request.user.is_superuser:
            has_full_perms = True
            can_grant_manager = True
            has_view_access = True
        elif hasattr(request.user, 'employee') and request.user.employee:
            if request.user.employee.role.slug == 'owner':
                has_full_perms = True
                can_grant_manager = True
                has_view_access = True
            elif request.user.employee.is_manager:
                has_full_perms = True
                has_view_access = True
            else:
                try:
                    access = request.user.employee.module_access
                    if access.employees_access in ['edit', 'full']:
                        has_full_perms = True
                        has_view_access = True
                except Exception:
                    pass
            
            # Everyone has view access to their own profile, but NOT necessarily full perms to edit it
            if request.user.employee.pk == pk:
                has_view_access = True
                # A regular employee editing their own profile shouldn't get full perms
                if not request.user.employee.is_manager:
                    has_full_perms = False

    if not has_view_access:
        messages.error(request, "You don't have access to edit other employee profiles.")
        return redirect('dashboard')

    if request.method == 'POST':
        user_form = EmployeeUserForm(request.POST, instance=user, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)
        emp_form = EmployeeForm(request.POST, request.FILES, instance=employee, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)

        if user_form.is_valid() and emp_form.is_valid():
            user = user_form.save(commit=False)
            password = user_form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()

            emp_form.save()

            messages.success(request, f'Employee {employee.full_name} updated successfully!')
            return redirect('employee_detail', pk=employee.pk)
    else:
        user_form = EmployeeUserForm(instance=user, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)
        emp_form = EmployeeForm(instance=employee, has_full_perms=has_full_perms, can_grant_manager=can_grant_manager)

    return render(request, 'accounts/employee_form.html', {
        'user_form': user_form,
        'emp_form': emp_form,
        'employee': employee,
        'title': f'Edit Employee: {employee.full_name}',
    })


@login_required
@check_module_access('employees', 'full')
def employee_module_access(request, pk):
    employee = get_object_or_404(Employee, pk=pk)

    # Owner/superuser always has full access — permissions page is unnecessary
    if employee.user.is_superuser or (employee.role and employee.role.slug == 'owner'):
        messages.info(request, f'{employee.full_name} is an Owner/Admin and already has full access. Permissions cannot be modified.')
        return redirect('employee_detail', pk=employee.pk)

    module_access, created = ModuleAccess.objects.get_or_create(employee=employee)

    if request.method == 'POST':
        form = ModuleAccessForm(request.POST, instance=module_access)
        if form.is_valid():
            form.save()
            # Invalidate cached module access for this user
            from django.core.cache import cache
            cache.delete(f'user_access_{employee.user_id}')
            messages.success(request, f'Module access for {employee.full_name} updated successfully!')
            return redirect('employee_detail', pk=employee.pk)
    else:
        form = ModuleAccessForm(instance=module_access)

    return render(request, 'accounts/module_access_form.html', {
        'form': form,
        'employee': employee,
    })


@login_required
@check_module_access('teams', 'view')
def team_list(request):
    teams = Team.objects.prefetch_related('leader', 'members').all()
    return render(request, 'accounts/team_list.html', {
        'teams': teams,
        'title': 'Teams Management',
    })


@login_required
@check_module_access('teams', 'edit')
def team_create(request):
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            messages.success(request, f'Team {team.name} created successfully.')
            return redirect('team_list')
    else:
        form = TeamForm()
    
    return render(request, 'accounts/team_form.html', {
        'form': form,
        'title': 'Create New Team',
    })


@login_required
@check_module_access('teams', 'edit')
def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, f'Team {team.name} updated successfully.')
            return redirect('team_list')
    else:
        form = TeamForm(instance=team)
    
    return render(request, 'accounts/team_form.html', {
        'form': form,
        'team': team,
        'title': f'Edit Team: {team.name}',
    })