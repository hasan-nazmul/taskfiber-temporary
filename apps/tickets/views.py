import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, F
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from urllib.parse import quote

from .models import Ticket, TicketComment, TicketStatusLog, TicketStockUsage
from .forms import (
    TicketCreateForm, TicketEditForm, TicketAssignForm,
    TicketStatusForm, TicketCommentForm, TicketStockUsageForm
)
from apps.accounts.models import Employee, Team
from apps.accounts.decorators import check_module_access
from apps.customers.models import Customer

logger = logging.getLogger(__name__)


def get_employee(request):
    """Helper to get employee from logged in user"""
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


def _generate_whatsapp_message(ticket):
    """Generate a WhatsApp-friendly message for a ticket"""
    lines = []
    lines.append(f"📋 *Ticket: {ticket.ticket_number}*")
    lines.append(f"Type: {ticket.get_ticket_type_display()}")

    if ticket.customer:
        lines.append(f"Customer: {ticket.customer.name}")
        lines.append(f"Phone: {ticket.customer.phone}")
        lines.append(f"Area: {ticket.customer.area.name}")
        lines.append(f"Address: {ticket.customer.address}")
    elif ticket.contact_name:
        lines.append(f"Contact: {ticket.contact_name}")
        lines.append(f"Phone: {ticket.contact_phone}")
        if ticket.contact_address:
            lines.append(f"Address: {ticket.contact_address}")

    if ticket.work_location:
        lines.append(f"Work Location: {ticket.work_location}")

    lines.append(f"Priority: {ticket.get_priority_display()}")

    if ticket.description:
        lines.append(f"Details: {ticket.description}")

    if ticket.scheduled_date:
        lines.append(f"Scheduled: {ticket.scheduled_date}")
        if ticket.scheduled_time_slot:
            lines.append(f"Time: {ticket.scheduled_time_slot}")

    if ticket.line_cut_reason:
        lines.append(f"Reason: {ticket.get_line_cut_reason_display()}")

    if ticket.assigned_to:
        lines.append(f"Assigned to: {ticket.assigned_to.full_name}")

    if ticket.status == 'resolved' and ticket.resolution_notes:
        lines.append(f"Resolution: {ticket.resolution_notes}")

    return '\n'.join(lines)


@login_required
@check_module_access('tickets', 'view')
def ticket_list(request):
    tickets = Ticket.objects.select_related(
        'customer', 'assigned_to', 'created_by', 'area'
    ).all()

    # Filters
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    ticket_type = request.GET.get('ticket_type', '')
    priority = request.GET.get('priority', '')
    assigned_to = request.GET.get('assigned_to', '')
    assigned_team = request.GET.get('assigned_team', '')
    date_range = request.GET.get('date_range', '')

    if search:
        tickets = tickets.filter(
            Q(ticket_number__icontains=search) |
            Q(title__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(customer__customer_id__icontains=search) |
            Q(contact_name__icontains=search) |
            Q(contact_phone__icontains=search)
        )
    if status:
        tickets = tickets.filter(status=status)
    if ticket_type:
        tickets = tickets.filter(ticket_type=ticket_type)
    if priority:
        tickets = tickets.filter(priority=priority)
    if assigned_to:
        if assigned_to == 'unassigned':
            tickets = tickets.filter(assigned_to__isnull=True)
        else:
            tickets = tickets.filter(assigned_to_id=assigned_to)
    if assigned_team:
        tickets = tickets.filter(assigned_team=assigned_team)

    today = timezone.now().date()
    if date_range == 'today':
        tickets = tickets.filter(created_at__date=today)
    elif date_range == 'this_week':
        start_of_week = today - timezone.timedelta(days=today.weekday())
        tickets = tickets.filter(created_at__date__gte=start_of_week)
    elif date_range == 'this_month':
        tickets = tickets.filter(created_at__date__year=today.year, created_at__date__month=today.month)

    # Pagination
    paginator = Paginator(tickets, 25)
    page = request.GET.get('page')
    try:
        tickets_page = paginator.page(page)
    except PageNotAnInteger:
        tickets_page = paginator.page(1)
    except EmptyPage:
        tickets_page = paginator.page(paginator.num_pages)

    employees = Employee.objects.filter(
        is_active=True
    ).exclude(
        role__slug__in=['owner', 'manager']
    ).select_related('user')

    context = {
        'tickets': tickets_page,
        'employees': employees,
        'filters': {
            'search': search,
            'status': status,
            'ticket_type': ticket_type,
            'priority': priority,
            'assigned_to': assigned_to,
            'assigned_team': assigned_team,
            'date_range': date_range,
        },
        'status_choices': Ticket.STATUS_CHOICES,
        'type_choices': Ticket.TICKET_TYPE_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'team_choices': Team.objects.all(),
    }
    return render(request, 'tickets/ticket_list.html', context)


def _get_filtered_tickets(request):
    """Shared filter logic for ticket list and export."""
    tickets = Ticket.objects.select_related(
        'customer', 'assigned_to', 'created_by', 'area'
    ).all()
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    ticket_type = request.GET.get('ticket_type', '')
    priority = request.GET.get('priority', '')
    assigned_to = request.GET.get('assigned_to', '')
    assigned_team = request.GET.get('assigned_team', '')
    date_range = request.GET.get('date_range', '')
    if search:
        tickets = tickets.filter(
            Q(ticket_number__icontains=search) | Q(title__icontains=search) |
            Q(customer__name__icontains=search) | Q(customer__customer_id__icontains=search) |
            Q(contact_name__icontains=search) | Q(contact_phone__icontains=search)
        )
    if status:
        tickets = tickets.filter(status=status)
    if ticket_type:
        tickets = tickets.filter(ticket_type=ticket_type)
    if priority:
        tickets = tickets.filter(priority=priority)
    if assigned_to:
        if assigned_to == 'unassigned':
            tickets = tickets.filter(assigned_to__isnull=True)
        else:
            tickets = tickets.filter(assigned_to_id=assigned_to)
    if assigned_team:
        tickets = tickets.filter(assigned_team=assigned_team)
    today = timezone.now().date()
    if date_range == 'today':
        tickets = tickets.filter(created_at__date=today)
    elif date_range == 'this_week':
        start_of_week = today - timezone.timedelta(days=today.weekday())
        tickets = tickets.filter(created_at__date__gte=start_of_week)
    elif date_range == 'this_month':
        tickets = tickets.filter(created_at__date__year=today.year, created_at__date__month=today.month)
    return tickets


@login_required
@check_module_access('tickets', 'view')
def ticket_export_csv(request):
    from utils.export_helpers import csv_response
    tickets = _get_filtered_tickets(request)
    headers = ['Ticket #', 'Type', 'Customer', 'Priority', 'Status', 'Assigned To', 'Area', 'Created']
    rows = [
        [t.ticket_number, t.get_ticket_type_display(),
         t.customer.name if t.customer else t.contact_name,
         t.get_priority_display(), t.get_status_display(),
         t.assigned_to.full_name if t.assigned_to else 'Unassigned',
         t.area.name if t.area else '',
         t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '']
        for t in tickets
    ]
    return csv_response('tickets.csv', headers, rows)


@login_required
@check_module_access('tickets', 'view')
def ticket_export_pdf(request):
    from utils.export_helpers import pdf_response
    tickets = _get_filtered_tickets(request)
    headers = ['Ticket #', 'Type', 'Customer', 'Priority', 'Status', 'Assigned To', 'Area', 'Created']
    rows = [
        [t.ticket_number, t.get_ticket_type_display(),
         t.customer.name if t.customer else t.contact_name,
         t.get_priority_display(), t.get_status_display(),
         t.assigned_to.full_name if t.assigned_to else 'Unassigned',
         t.area.name if t.area else '',
         t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '']
        for t in tickets
    ]
    return pdf_response('tickets.pdf', 'Tickets Report', headers, rows, landscape_mode=True)


@login_required
@check_module_access('tickets', 'edit')
def ticket_create(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = TicketCreateForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = employee

            # Auto-set status based on assignment
            if ticket.assigned_to:
                ticket.status = 'assigned'
                ticket.assigned_at = timezone.now()

            # Auto-set title if empty
            if not ticket.title:
                customer_name = ''
                if ticket.customer:
                    customer_name = ticket.customer.name
                elif ticket.contact_name:
                    customer_name = ticket.contact_name
                ticket.title = f"{ticket.get_ticket_type_display()} - {customer_name}"

            ticket.save()

            # Log status
            TicketStatusLog.objects.create(
                ticket=ticket,
                old_status='',
                new_status=ticket.status,
                changed_by=employee,
                notes='Ticket created'
            )

            messages.success(request, f'Ticket {ticket.ticket_number} created successfully!')
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        initial = {}
        # Pre-fill customer if passed in URL
        customer_id = request.GET.get('customer')
        if customer_id:
            try:
                customer = Customer.objects.get(pk=customer_id)
                initial['customer'] = customer
                initial['area'] = customer.area
            except Customer.DoesNotExist:
                pass

        form = TicketCreateForm(initial=initial)

    return render(request, 'tickets/ticket_form.html', {
        'form': form,
        'title': 'Create New Ticket',
    })


@login_required
@check_module_access('tickets', 'view')
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related(
            'customer', 'assigned_to', 'created_by', 'resolved_by', 'area',
            'customer__area', 'customer__package'
        ),
        pk=pk
    )

    employee = get_employee(request)

    # Forms
    comment_form = TicketCommentForm()
    assign_form = TicketAssignForm(initial={
        'assigned_team': ticket.assigned_team,
        'assigned_to': ticket.assigned_to,
    })
    status_form = TicketStatusForm(initial={
        'status': ticket.status,
    })
    stock_form = TicketStockUsageForm()

    # Handle POST actions — require employee profile AND edit access
    if request.method == 'POST':
        if not employee:
            messages.error(request, 'Employee profile required to perform this action.')
            return redirect('ticket_detail', pk=ticket.pk)

        # Verify the user has at least 'edit' access for POST actions
        has_edit_access = False
        if request.user.is_superuser:
            has_edit_access = True
        elif hasattr(request.user, 'employee') and request.user.employee:
            if request.user.employee.is_manager:
                has_edit_access = True
            else:
                try:
                    access = request.user.employee.module_access
                    if access.tickets_access in ('edit', 'full'):
                        has_edit_access = True
                except Exception:
                    pass

        if not has_edit_access:
            messages.error(request, "You don't have permission to modify tickets.")
            return redirect('ticket_detail', pk=ticket.pk)

    # Handle comment submission
    if request.method == 'POST' and 'add_comment' in request.POST:
        comment_form = TicketCommentForm(request.POST)
        if comment_form.is_valid():
            try:
                comment = comment_form.save(commit=False)
                comment.ticket = ticket
                comment.author = employee
                comment.save()
                messages.success(request, 'Comment added.')
            except Exception as e:
                logger.error(f'Comment save failed on ticket {pk}: {e}')
                messages.error(request, 'Failed to add comment.')
            return redirect('ticket_detail', pk=ticket.pk)

    # Handle assignment
    if request.method == 'POST' and 'assign_ticket' in request.POST:
        assign_form = TicketAssignForm(request.POST)
        if assign_form.is_valid():
            try:
                old_assigned = ticket.assigned_to
                ticket.assigned_team = assign_form.cleaned_data['assigned_team']
                ticket.assigned_to = assign_form.cleaned_data['assigned_to']

                if ticket.assigned_to:
                    # Auto-set status to 'assigned' if currently open or re-assigning
                    if ticket.status in ('open',):
                        old_status = ticket.status
                        ticket.status = 'assigned'
                        ticket.assigned_at = timezone.now()

                        TicketStatusLog.objects.create(
                            ticket=ticket,
                            old_status=old_status,
                            new_status='assigned',
                            changed_by=employee,
                            notes=f'Assigned to {ticket.assigned_to.full_name}'
                        )
                    elif not old_assigned:
                        # First time assigning but ticket already progressed
                        ticket.assigned_at = timezone.now()
                else:
                    # Un-assigning: revert to open if status was 'assigned'
                    if ticket.status == 'assigned':
                        old_status = ticket.status
                        ticket.status = 'open'
                        ticket.assigned_at = None

                        TicketStatusLog.objects.create(
                            ticket=ticket,
                            old_status=old_status,
                            new_status='open',
                            changed_by=employee,
                            notes='Unassigned — reverted to open'
                        )

                ticket.save()

                notes = assign_form.cleaned_data.get('notes', '')
                if notes:
                    TicketComment.objects.create(
                        ticket=ticket,
                        author=employee,
                        comment=f"Assignment note: {notes}",
                        is_internal=True
                    )

                messages.success(request, 'Ticket assigned successfully.')
            except Exception as e:
                logger.error(f'Assignment failed on ticket {pk}: {e}')
                messages.error(request, 'Failed to assign ticket.')
            return redirect('ticket_detail', pk=ticket.pk)

    # Handle status change
    if request.method == 'POST' and 'change_status' in request.POST:
        status_form = TicketStatusForm(request.POST)
        if status_form.is_valid():
            try:
                old_status = ticket.status
                new_status = status_form.cleaned_data['status']
                notes = status_form.cleaned_data.get('notes', '')

                # Guard: prevent manual 'assigned' status
                if new_status == 'assigned':
                    messages.error(request, 'Cannot manually set status to Assigned. Assign an employee instead.')
                    return redirect('ticket_detail', pk=ticket.pk)

                if old_status == new_status:
                    messages.info(request, 'Status unchanged.')
                    return redirect('ticket_detail', pk=ticket.pk)

                ticket.status = new_status

                if new_status == 'resolved':
                    ticket.resolved_at = timezone.now()
                    ticket.resolved_by = employee
                    ticket.resolution_notes = status_form.cleaned_data.get(
                        'resolution_notes', ''
                    ) or notes

                if new_status == 'closed':
                    ticket.closed_at = timezone.now()

                ticket.save()

                TicketStatusLog.objects.create(
                    ticket=ticket,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=employee,
                    notes=notes
                )

                messages.success(
                    request,
                    f'Status changed: {old_status} → {new_status}'
                )
            except Exception as e:
                logger.error(f'Status change failed on ticket {pk}: {e}')
                messages.error(request, 'Failed to change status.')
            return redirect('ticket_detail', pk=ticket.pk)

    # Handle stock usage
    if request.method == 'POST' and 'add_stock' in request.POST:
        stock_form = TicketStockUsageForm(request.POST)
        if stock_form.is_valid():
            try:
                stock_usage = stock_form.save(commit=False)
                stock_usage.ticket = ticket
                stock_usage.added_by = employee

                # Reduce stock atomically
                stock_item = stock_usage.stock_item
                from apps.stock.models import StockItem as SI
                if stock_item.quantity_in_stock >= stock_usage.quantity_used:
                    updated = SI.objects.filter(
                        pk=stock_item.pk, quantity_in_stock__gte=stock_usage.quantity_used
                    ).update(quantity_in_stock=F('quantity_in_stock') - stock_usage.quantity_used)
                    if updated:
                        stock_item.refresh_from_db()
                        stock_usage.save()

                    # Create stock transaction
                    from apps.stock.models import StockTransaction
                    StockTransaction.objects.create(
                        stock_item=stock_item,
                        transaction_type='used',
                        quantity=-stock_usage.quantity_used,
                        ticket=ticket,
                        notes=f'Used on ticket {ticket.ticket_number}',
                        performed_by=employee,
                    )

                    messages.success(request, f'{stock_item.name} x{stock_usage.quantity_used} recorded.')
                else:
                    messages.error(
                        request,
                        f'Not enough stock. Available: {stock_item.quantity_in_stock}'
                    )
            except Exception as e:
                logger.error(f'Stock usage failed on ticket {pk}: {e}')
                messages.error(request, 'Failed to record stock usage.')

            return redirect('ticket_detail', pk=ticket.pk)

    # Get related data
    comments = ticket.comments.select_related('author', 'author__user').all()
    status_logs = ticket.status_logs.select_related('changed_by', 'changed_by__user').all()
    stock_used = ticket.stock_used.select_related('stock_item', 'added_by').all()

    timeline = []
    for c in comments:
        timeline.append({'type': 'comment', 'obj': c, 'timestamp': c.created_at})
    for log in status_logs:
        timeline.append({'type': 'status_change', 'obj': log, 'timestamp': log.created_at})
    for su in stock_used:
        timeline.append({'type': 'stock_used', 'obj': su, 'timestamp': su.created_at})

    sort_order = request.GET.get('sort', 'desc')
    timeline.sort(key=lambda x: x['timestamp'], reverse=(sort_order == 'desc'))

    # WhatsApp message template
    whatsapp_msg = _generate_whatsapp_message(ticket)

    # WhatsApp URL for cable team notification
    whatsapp_url = ''
    if ticket.assigned_to and ticket.assigned_to.whatsapp_number:
        phone = ticket.assigned_to.whatsapp_number.replace('+', '').replace(' ', '').replace('-', '')
        whatsapp_url = f"https://wa.me/{phone}?text={quote(whatsapp_msg)}"

    context = {
        'ticket': ticket,
        'timeline': timeline,
        'sort_order': sort_order,
        'stock_used': stock_used,
        'comment_form': comment_form,
        'assign_form': assign_form,
        'status_form': status_form,
        'stock_form': stock_form,
        'whatsapp_msg': whatsapp_msg,
        'whatsapp_url': whatsapp_url,
        'employee': employee,
    }
    return render(request, 'tickets/ticket_detail.html', context)


@login_required
@check_module_access('tickets', 'edit')
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('ticket_list')

    if request.method == 'POST':
        form = TicketEditForm(request.POST, instance=ticket)
        if form.is_valid():
            old_status = ticket.status
            updated_ticket = form.save(commit=False)

            # Prevent manual "assigned" status without an assignee
            if updated_ticket.status == 'assigned' and not updated_ticket.assigned_to:
                updated_ticket.status = 'open'

            # Auto-set status to "assigned" when assigning from open
            if updated_ticket.assigned_to and updated_ticket.status == 'open':
                updated_ticket.status = 'assigned'

            # Track assignment
            if updated_ticket.assigned_to and not ticket.assigned_at:
                updated_ticket.assigned_at = timezone.now()

            # Track resolution
            if updated_ticket.status == 'resolved' and old_status != 'resolved':
                updated_ticket.resolved_at = timezone.now()
                updated_ticket.resolved_by = employee

            if updated_ticket.status == 'closed' and old_status != 'closed':
                updated_ticket.closed_at = timezone.now()

            updated_ticket.save()

            # Log status change if changed
            new_status = updated_ticket.status
            if old_status != new_status and employee:
                TicketStatusLog.objects.create(
                    ticket=updated_ticket,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=employee,
                    notes='Updated via edit form'
                )

            messages.success(request, f'Ticket {ticket.ticket_number} updated.')
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketEditForm(instance=ticket)

    return render(request, 'tickets/ticket_form.html', {
        'form': form,
        'ticket': ticket,
        'title': f'Edit Ticket: {ticket.ticket_number}',
    })


@login_required
@check_module_access('tickets', 'view')
def my_tickets(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('dashboard')

    tickets = Ticket.objects.filter(
        assigned_to=employee
    ).select_related('customer', 'area').order_by('-created_at')

    # Filters
    status = request.GET.get('status', '')
    if status:
        tickets = tickets.filter(status=status)
    else:
        # Default: show only active tickets
        tickets = tickets.exclude(status__in=['closed', 'cancelled'])

    context = {
        'tickets': tickets,
        'employee': employee,
        'filters': {'status': status},
        'status_choices': Ticket.STATUS_CHOICES,
    }
    return render(request, 'tickets/my_tickets.html', context)


@login_required
@require_POST
@check_module_access('tickets', 'edit')
def ticket_quick_resolve(request, pk):
    """Quick resolve a ticket from list/my tickets"""
    ticket = get_object_or_404(Ticket, pk=pk)
    employee = get_employee(request)

    if not employee:
        messages.error(request, 'Employee profile required.')
        return redirect('ticket_list')

    if ticket.status in ('resolved', 'closed', 'cancelled'):
        messages.warning(request, f'Ticket {ticket.ticket_number} is already {ticket.get_status_display()}.')
        return redirect('ticket_list')

    try:
        old_status = ticket.status
        ticket.status = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.resolved_by = employee
        ticket.resolution_notes = request.POST.get('resolution_notes', 'Quick resolved')
        ticket.save()

        TicketStatusLog.objects.create(
            ticket=ticket,
            old_status=old_status,
            new_status='resolved',
            changed_by=employee,
            notes='Quick resolved'
        )
        messages.success(request, f'Ticket {ticket.ticket_number} resolved.')
    except Exception as e:
        logger.error(f'Quick resolve failed for ticket {pk}: {e}')
        messages.error(request, 'Failed to resolve ticket. Please try again.')

    return redirect(request.META.get('HTTP_REFERER', '') if request.META.get('HTTP_REFERER', '').startswith('/') else 'ticket_list')


@login_required
@check_module_access('tickets', 'edit')
def customer_search_api(request):
    """API endpoint for searching customers (for AJAX in ticket form)"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    # Sanitize - limit length to prevent abuse
    query = query[:100]

    try:
        customers = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(customer_id__icontains=query) |
            Q(phone__icontains=query)
        ).select_related('area')[:10]

        results = [{
            'id': c.pk,
            'text': f"{c.customer_id} - {c.name} ({c.phone})",
            'name': c.name,
            'phone': c.phone,
            'address': c.address,
            'area': c.area.name if c.area else '',
            'area_id': c.area_id,
        } for c in customers]
    except Exception:
        results = []

    return JsonResponse({'results': results})


TICKET_IMPORT_HEADERS = ['Type', 'Source', 'Contact Name', 'Contact Phone', 'Contact Address', 'Title', 'Description', 'Priority']


@login_required
@check_module_access('tickets', 'edit')
def ticket_import_template(request):
    from utils.import_helpers import sample_csv_response
    return sample_csv_response('ticket_import_template.csv', TICKET_IMPORT_HEADERS)


@login_required
@check_module_access('tickets', 'edit')
def ticket_import_csv(request):
    from utils.import_helpers import parse_csv
    from django.db import transaction

    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('ticket_list')

    context = {
        'module_name': 'Tickets',
        'back_url': '/tickets/',
        'template_url': '/tickets/import/template/',
        'expected_columns': TICKET_IMPORT_HEADERS,
    }

    valid_types = dict(Ticket.TICKET_TYPE_CHOICES)
    valid_sources = dict(Ticket.SOURCE_CHOICES)
    valid_priorities = dict(Ticket.PRIORITY_CHOICES)

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return render(request, 'common/csv_import.html', context)

        headers, rows = parse_csv(csv_file)
        created = 0
        errors = []

        for i, row in enumerate(rows, start=2):
            try:
                ticket_type = row.get('Type', '').strip().lower().replace(' ', '_')
                if ticket_type not in valid_types:
                    errors.append({'row': i, 'message': f'Invalid type "{row.get("Type", "")}"'})
                    continue

                source = row.get('Source', 'phone').strip().lower().replace(' ', '_').replace('-', '_')
                if source not in valid_sources:
                    source = 'phone'

                priority = row.get('Priority', 'medium').strip().lower()
                if priority not in valid_priorities:
                    priority = 'medium'

                contact_name = row.get('Contact Name', '').strip()
                title = row.get('Title', '').strip()
                if not title and not contact_name:
                    errors.append({'row': i, 'message': 'Title or Contact Name is required'})
                    continue

                with transaction.atomic():
                    ticket = Ticket(
                        ticket_type=ticket_type,
                        source=source,
                        created_by=employee,
                        contact_name=contact_name,
                        contact_phone=row.get('Contact Phone', '').strip(),
                        contact_address=row.get('Contact Address', '').strip(),
                        title=title or f"{valid_types[ticket_type]} - {contact_name}",
                        description=row.get('Description', '').strip(),
                        priority=priority,
                        status='open',
                    )
                    ticket.save()

                    TicketStatusLog.objects.create(
                        ticket=ticket,
                        old_status='',
                        new_status='open',
                        changed_by=employee,
                        notes='Imported from CSV',
                    )
                    created += 1
            except Exception as e:
                errors.append({'row': i, 'message': str(e)})

        context['results'] = {'created': created, 'skipped': 0, 'errors': errors}

    return render(request, 'common/csv_import.html', context)