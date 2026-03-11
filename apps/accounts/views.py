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


@login_required
def dashboard(request):
    from apps.tickets.models import Ticket
    from apps.stock.models import StockItem

    today = timezone.now().date()

    # Ticket stats
    ticket_stats = {
        'open': Ticket.objects.filter(status='open').count(),
        'assigned': Ticket.objects.filter(status='assigned').count(),
        'in_progress': Ticket.objects.filter(status='in_progress').count(),
        'resolved_today': Ticket.objects.filter(
            status='resolved', resolved_at__date=today
        ).count(),
        'new_today': Ticket.objects.filter(created_at__date=today).count(),
        'total_open': Ticket.objects.exclude(
            status__in=['resolved', 'closed', 'cancelled']
        ).count(),
    }

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

    context = {
        'employees': employees,
        'roles': roles,
        'filters': {
            'department': department,
            'role': role,
            'status': status,
            'search': search,
        }
    }
    return render(request, 'accounts/employee_list.html', context)


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
    is_target_owner_admin = employee.user.is_superuser or (employee.role and employee.role.slug == 'owner')
    is_requester_owner_admin = request.user.is_superuser or (hasattr(request.user, 'employee') and request.user.employee and request.user.employee.role and request.user.employee.role.slug == 'owner')

    if is_target_owner_admin and not is_requester_owner_admin:
        messages.error(request, "You do not have permission to modify module access for an Owner or System Admin.")
        return redirect('dashboard')

    module_access, created = ModuleAccess.objects.get_or_create(employee=employee)

    if request.method == 'POST':
        form = ModuleAccessForm(request.POST, instance=module_access)
        if form.is_valid():
            form.save()
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