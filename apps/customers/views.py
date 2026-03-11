from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.views.decorators.http import require_POST

from .models import Customer, Area, Package
from .forms import CustomerForm, AreaForm, PackageForm
from apps.accounts.decorators import check_module_access


@login_required
@check_module_access('customers', 'view')
def customer_list(request):
    customers = Customer.objects.select_related('area', 'package').all()

    # Filters
    search = request.GET.get('search', '')
    area = request.GET.get('area', '')
    status = request.GET.get('status', '')
    package = request.GET.get('package', '')
    connection_type = request.GET.get('connection_type', '')

    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(customer_id__icontains=search) |
            Q(phone__icontains=search) |
            Q(pppoe_username__icontains=search) |
            Q(address__icontains=search)
        )
    if area:
        customers = customers.filter(area_id=area)
    if status:
        customers = customers.filter(status=status)
    if package:
        customers = customers.filter(package_id=package)
    if connection_type:
        customers = customers.filter(connection_type=connection_type)

    areas = Area.objects.filter(is_active=True)
    packages = Package.objects.filter(is_active=True)

    # Pagination
    paginator = Paginator(customers, 30)
    page = request.GET.get('page')
    try:
        customers_page = paginator.page(page)
    except PageNotAnInteger:
        customers_page = paginator.page(1)
    except EmptyPage:
        customers_page = paginator.page(paginator.num_pages)

    context = {
        'customers': customers_page,
        'areas': areas,
        'packages': packages,
        'filters': {
            'search': search,
            'area': area,
            'status': status,
            'package': package,
            'connection_type': connection_type,
        },
        'status_choices': Customer.STATUS_CHOICES,
        'connection_type_choices': Customer.CONNECTION_TYPE_CHOICES,
    }
    return render(request, 'customers/customer_list.html', context)


@login_required
@check_module_access('customers', 'edit')
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer {customer.name} created successfully!')
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'customers/customer_form.html', {
        'form': form,
        'title': 'Add New Customer',
    })


@login_required
@check_module_access('customers', 'view')
def customer_detail(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related('area', 'package', 'referred_by'), pk=pk
    )

    # Get tickets for this customer
    from apps.tickets.models import Ticket
    tickets_query = Ticket.objects.filter(customer=customer).order_by('-created_at')
    open_ticket_count = tickets_query.filter(
        status__in=['open', 'assigned', 'in_progress']
    ).count()
    tickets = tickets_query[:20]

    context = {
        'customer': customer,
        'tickets': tickets,
        'open_ticket_count': open_ticket_count,
    }
    return render(request, 'customers/customer_detail.html', context)


@login_required
@check_module_access('customers', 'edit')
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer {customer.name} updated successfully!')
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/customer_form.html', {
        'form': form,
        'customer': customer,
        'title': f'Edit Customer: {customer.name}',
    })


# --- Area / Zone Management ---

@login_required
@check_module_access('zones', 'view')
def area_list(request):
    areas = Area.objects.annotate(customer_count=Count('customers'))
    return render(request, 'customers/area_list.html', {'areas': areas})


@login_required
@check_module_access('zones', 'edit')
def area_create(request):
    if request.method == 'POST':
        form = AreaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Zone created successfully!')
            return redirect('area_list')
    else:
        form = AreaForm()

    return render(request, 'customers/area_form.html', {
        'form': form,
        'title': 'Add New Zone',
    })


@login_required
@check_module_access('zones', 'edit')
def area_edit(request, pk):
    area = get_object_or_404(Area, pk=pk)

    if request.method == 'POST':
        form = AreaForm(request.POST, instance=area)
        if form.is_valid():
            form.save()
            messages.success(request, f'Zone {area.name} updated successfully!')
            return redirect('area_list')
    else:
        form = AreaForm(instance=area)

    return render(request, 'customers/area_form.html', {
        'form': form,
        'area': area,
        'title': f'Edit Zone: {area.name}',
    })


@login_required
@require_POST
@check_module_access('zones', 'edit')
def area_toggle_active(request, pk):
    area = get_object_or_404(Area, pk=pk)
    area.is_active = not area.is_active
    area.save(update_fields=['is_active'])
    status = 'activated' if area.is_active else 'deactivated'
    messages.success(request, f'Zone {area.name} has been {status}. Customers remain unaffected.')
    return redirect('area_list')


# --- Package Management ---

@login_required
@check_module_access('customers', 'view')
def package_list(request):
    packages = Package.objects.annotate(customer_count=Count('customers'))
    return render(request, 'customers/package_list.html', {'packages': packages})


@login_required
@check_module_access('customers', 'edit')
def package_create(request):
    if request.method == 'POST':
        form = PackageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Package created successfully!')
            return redirect('package_list')
    else:
        form = PackageForm()

    return render(request, 'customers/package_form.html', {
        'form': form,
        'title': 'Add New Package',
    })


@login_required
@check_module_access('customers', 'edit')
def package_edit(request, pk):
    pkg = get_object_or_404(Package, pk=pk)

    if request.method == 'POST':
        form = PackageForm(request.POST, instance=pkg)
        if form.is_valid():
            form.save()
            messages.success(request, f'Package {pkg.name} updated successfully!')
            return redirect('package_list')
    else:
        form = PackageForm(instance=pkg)

    return render(request, 'customers/package_form.html', {
        'form': form,
        'package': pkg,
        'title': f'Edit Package: {pkg.name}',
    })