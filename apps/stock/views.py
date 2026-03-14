from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, F, Sum, Count

from .models import StockCategory, StockItem, StockTransaction
from .forms import (
    StockCategoryForm, StockItemForm, StockPurchaseForm,
    StockIssueForm, StockReturnForm, StockAdjustmentForm
)
from apps.accounts.models import Employee
from apps.accounts.decorators import check_module_access
from utils.export_helpers import csv_response, pdf_response


def get_employee(request):
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


@login_required
@check_module_access('stock', 'view')
def stock_list(request):
    items = StockItem.objects.select_related('category').all()

    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    low_stock = request.GET.get('low_stock', '')
    status = request.GET.get('status', '')

    if search:
        items = items.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(brand__icontains=search) |
            Q(model_number__icontains=search)
        )
    if category:
        items = items.filter(category_id=category)
    if low_stock:
        items = items.filter(quantity_in_stock__lte=F('minimum_stock_level'))
    if status:
        if status == 'active':
            items = items.filter(is_active=True)
        elif status == 'inactive':
            items = items.filter(is_active=False)

    categories = StockCategory.objects.all()

    total_items = StockItem.objects.filter(is_active=True).count()
    low_stock_count = StockItem.objects.filter(
        is_active=True,
        quantity_in_stock__lte=F('minimum_stock_level')
    ).count()
    out_of_stock_count = StockItem.objects.filter(
        is_active=True, quantity_in_stock=0
    ).count()
    total_value = StockItem.objects.filter(is_active=True).aggregate(
        total=Sum(F('quantity_in_stock') * F('purchase_price'))
    )['total'] or 0

    context = {
        'items': items,
        'categories': categories,
        'filters': {
            'search': search,
            'category': category,
            'low_stock': low_stock,
            'status': status,
        },
        'stats': {
            'total_items': total_items,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'total_value': total_value,
        }
    }
    return render(request, 'stock/stock_list.html', context)




@login_required
@check_module_access('stock', 'edit')
def stock_item_create(request):
    if request.method == 'POST':
        form = StockItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(request, f'Stock item "{item.name}" created successfully!')
            return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockItemForm()

    return render(request, 'stock/stock_item_form.html', {
        'form': form,
        'title': 'Add New Stock Item',
    })


@login_required
@check_module_access('stock', 'view')
def stock_item_detail(request, pk):
    item = get_object_or_404(StockItem.objects.select_related('category'), pk=pk)
    transactions = item.transactions.select_related(
        'performed_by', 'performed_by__user', 'issued_to', 'ticket'
    ).all()[:50]

    context = {
        'item': item,
        'transactions': transactions,
    }
    return render(request, 'stock/stock_item_detail.html', context)


@login_required
@check_module_access('stock', 'edit')
def stock_item_edit(request, pk):
    item = get_object_or_404(StockItem, pk=pk)

    if request.method == 'POST':
        form = StockItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Stock item "{item.name}" updated.')
            return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockItemForm(instance=item)

    return render(request, 'stock/stock_item_form.html', {
        'form': form,
        'item': item,
        'title': f'Edit: {item.name}',
    })


@login_required
@check_module_access('stock', 'edit')
def stock_purchase(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('stock_list')

    if request.method == 'POST':
        form = StockPurchaseForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data['stock_item']
            quantity = form.cleaned_data['quantity']
            unit_price = form.cleaned_data.get('unit_price') or item.purchase_price

            item.quantity_in_stock = F('quantity_in_stock') + quantity
            if unit_price:
                item.purchase_price = unit_price
            item.save()
            item.refresh_from_db()

            StockTransaction.objects.create(
                stock_item=item,
                transaction_type='purchase',
                quantity=quantity,
                unit_price=unit_price,
                vendor_name=form.cleaned_data.get('vendor_name', ''),
                invoice_number=form.cleaned_data.get('invoice_number', ''),
                notes=form.cleaned_data.get('notes', ''),
                performed_by=employee,
            )

            messages.success(
                request,
                f'Purchased {quantity} x {item.name}. New stock: {item.quantity_in_stock}'
            )
            return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockPurchaseForm()

    return render(request, 'stock/stock_transaction_form.html', {
        'form': form,
        'title': 'Purchase / Restock',
        'icon': 'bi-cart-plus',
        'btn_class': 'btn-success',
        'btn_text': 'Record Purchase',
    })


@login_required
@check_module_access('stock', 'edit')
def stock_issue(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('stock_list')

    if request.method == 'POST':
        form = StockIssueForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data['stock_item']
            quantity = form.cleaned_data['quantity']
            issued_to = form.cleaned_data['issued_to']

            if item.quantity_in_stock < quantity:
                messages.error(
                    request,
                    f'Not enough stock. Available: {item.quantity_in_stock} {item.get_unit_display()}'
                )
            else:
                updated = StockItem.objects.filter(
                    pk=item.pk, quantity_in_stock__gte=quantity
                ).update(quantity_in_stock=F('quantity_in_stock') - quantity)
                if not updated:
                    messages.error(request, 'Stock changed while processing. Please try again.')
                else:
                    item.refresh_from_db()

                StockTransaction.objects.create(
                    stock_item=item,
                    transaction_type='issue',
                    quantity=-quantity,
                    issued_to=issued_to,
                    notes=form.cleaned_data.get('notes', ''),
                    performed_by=employee,
                )

                messages.success(
                    request,
                    f'Issued {quantity} x {item.name} to {issued_to.full_name}. Remaining: {item.quantity_in_stock}'
                )
                return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockIssueForm()

    return render(request, 'stock/stock_transaction_form.html', {
        'form': form,
        'title': 'Issue Stock to Technician',
        'icon': 'bi-box-arrow-right',
        'btn_class': 'btn-warning',
        'btn_text': 'Issue Stock',
    })


@login_required
@check_module_access('stock', 'edit')
def stock_return(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('stock_list')

    if request.method == 'POST':
        form = StockReturnForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data['stock_item']
            quantity = form.cleaned_data['quantity']
            returned_by = form.cleaned_data.get('returned_by')

            item.quantity_in_stock = F('quantity_in_stock') + quantity
            item.save()
            item.refresh_from_db()

            StockTransaction.objects.create(
                stock_item=item,
                transaction_type='return',
                quantity=quantity,
                issued_to=returned_by,
                notes=form.cleaned_data.get('notes', ''),
                performed_by=employee,
            )

            messages.success(
                request,
                f'Returned {quantity} x {item.name}. New stock: {item.quantity_in_stock}'
            )
            return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockReturnForm()

    return render(request, 'stock/stock_transaction_form.html', {
        'form': form,
        'title': 'Return Stock',
        'icon': 'bi-box-arrow-in-left',
        'btn_class': 'btn-info',
        'btn_text': 'Record Return',
    })


@login_required
@check_module_access('stock', 'edit')
def stock_adjustment(request):
    employee = get_employee(request)
    if not employee:
        messages.error(request, 'Your account is not linked to an employee profile.')
        return redirect('stock_list')

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            item = form.cleaned_data['stock_item']
            quantity = form.cleaned_data['quantity']
            adjustment_type = form.cleaned_data['adjustment_type']
            reason = form.cleaned_data['reason']

            if adjustment_type == 'add':
                StockItem.objects.filter(pk=item.pk).update(
                    quantity_in_stock=F('quantity_in_stock') + quantity
                )
                txn_quantity = quantity
            else:
                if item.quantity_in_stock < quantity:
                    messages.error(
                        request,
                        f'Cannot remove {quantity}. Current stock: {item.quantity_in_stock}'
                    )
                    return render(request, 'stock/stock_transaction_form.html', {
                        'form': form,
                        'title': 'Manual Adjustment',
                        'icon': 'bi-sliders',
                        'btn_class': 'btn-secondary',
                        'btn_text': 'Submit Adjustment',
                    })
                updated = StockItem.objects.filter(
                    pk=item.pk, quantity_in_stock__gte=quantity
                ).update(quantity_in_stock=F('quantity_in_stock') - quantity)
                if not updated:
                    messages.error(request, 'Stock changed while processing. Please try again.')
                    return redirect('stock_adjustment')
                txn_quantity = -quantity

            item.refresh_from_db()

            StockTransaction.objects.create(
                stock_item=item,
                transaction_type='adjustment',
                quantity=txn_quantity,
                notes=f"Adjustment: {reason}",
                performed_by=employee,
            )

            messages.success(
                request,
                f'Adjusted {item.name}. New stock: {item.quantity_in_stock}'
            )
            return redirect('stock_item_detail', pk=item.pk)
    else:
        form = StockAdjustmentForm()

    return render(request, 'stock/stock_transaction_form.html', {
        'form': form,
        'title': 'Manual Stock Adjustment',
        'icon': 'bi-sliders',
        'btn_class': 'btn-secondary',
        'btn_text': 'Submit Adjustment',
    })


@login_required
@check_module_access('stock', 'view')
def stock_transactions(request):
    transactions = StockTransaction.objects.select_related(
        'stock_item', 'performed_by', 'performed_by__user',
        'issued_to', 'issued_to__user', 'ticket'
    ).all()

    search = request.GET.get('search', '')
    txn_type = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        transactions = transactions.filter(
            Q(stock_item__name__icontains=search) |
            Q(vendor_name__icontains=search) |
            Q(invoice_number__icontains=search) |
            Q(notes__icontains=search)
        )
    if txn_type:
        transactions = transactions.filter(transaction_type=txn_type)
    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)

    context = {
        'transactions': transactions[:100],
        'filters': {
            'search': search,
            'type': txn_type,
            'date_from': date_from,
            'date_to': date_to,
        },
        'type_choices': StockTransaction.TRANSACTION_TYPES,
    }
    return render(request, 'stock/stock_transactions.html', context)


@login_required
@check_module_access('stock', 'view')
def stock_category_list(request):
    categories = StockCategory.objects.annotate(
        item_count=Count('items')
    )
    return render(request, 'stock/category_list.html', {'categories': categories})


@login_required
@check_module_access('stock', 'edit')
def stock_category_create(request):
    if request.method == 'POST':
        form = StockCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created!')
            return redirect('stock_category_list')
    else:
        form = StockCategoryForm()

    return render(request, 'stock/category_form.html', {
        'form': form,
        'title': 'Add Stock Category',
    })


@login_required
@check_module_access('stock', 'edit')
def stock_category_edit(request, pk):
    category = get_object_or_404(StockCategory, pk=pk)

    if request.method == 'POST':
        form = StockCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated.')
            return redirect('stock_category_list')
    else:
        form = StockCategoryForm(instance=category)

    return render(request, 'stock/category_form.html', {
        'form': form,
        'category': category,
        'title': f'Edit Category: {category.name}',
    })


def _filtered_stock_items(request):
    """Apply stock list filters from GET params and return queryset."""
    items = StockItem.objects.select_related('category').all()
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    low_stock = request.GET.get('low_stock', '')
    status = request.GET.get('status', '')
    if search:
        items = items.filter(
            Q(name__icontains=search) | Q(sku__icontains=search) |
            Q(brand__icontains=search) | Q(model_number__icontains=search)
        )
    if category:
        items = items.filter(category_id=category)
    if low_stock:
        items = items.filter(quantity_in_stock__lte=F('minimum_stock_level'))
    if status == 'active':
        items = items.filter(is_active=True)
    elif status == 'inactive':
        items = items.filter(is_active=False)
    return items


def _stock_export_data(items):
    headers = ['SKU', 'Name', 'Category', 'In Stock', 'Min Level', 'Unit', 'Buy Price', 'Sell Price', 'Status']
    rows = []
    for item in items:
        rows.append([
            item.sku, item.name, item.category.name if item.category else '',
            item.quantity_in_stock, item.minimum_stock_level,
            item.get_unit_display(), item.purchase_price, item.selling_price,
            'Active' if item.is_active else 'Inactive',
        ])
    return headers, rows


@login_required
@check_module_access('stock', 'view')
def stock_export_csv(request):
    items = _filtered_stock_items(request)
    headers, rows = _stock_export_data(items)
    return csv_response('stock_items.csv', headers, rows)


@login_required
@check_module_access('stock', 'view')
def stock_export_pdf(request):
    items = _filtered_stock_items(request)
    headers, rows = _stock_export_data(items)
    return pdf_response('stock_items.pdf', 'Stock Inventory Report', headers, rows, landscape_mode=True)


STOCK_IMPORT_HEADERS = ['Name', 'Category', 'SKU', 'Brand', 'Model', 'Unit', 'Quantity', 'Min Level', 'Buy Price', 'Sell Price']


@login_required
@check_module_access('stock', 'edit')
def stock_import_template(request):
    from utils.import_helpers import sample_csv_response
    return sample_csv_response('stock_import_template.csv', STOCK_IMPORT_HEADERS)


@login_required
@check_module_access('stock', 'edit')
def stock_import_csv(request):
    from utils.import_helpers import parse_csv
    from django.db import transaction
    from django.utils.text import slugify

    context = {
        'module_name': 'Stock Items',
        'back_url': '/stock/',
        'template_url': '/stock/import/template/',
        'expected_columns': STOCK_IMPORT_HEADERS,
    }

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return render(request, 'common/csv_import.html', context)

        headers, rows = parse_csv(csv_file)
        created = 0
        skipped = 0
        errors = []
        valid_units = [c[0] for c in StockItem.UNIT_CHOICES]

        for i, row in enumerate(rows, start=2):
            try:
                name = row.get('Name', '').strip()
                if not name:
                    errors.append({'row': i, 'message': 'Name is required'})
                    continue

                sku = row.get('SKU', '').strip()
                if sku and StockItem.objects.filter(sku=sku).exists():
                    skipped += 1
                    continue

                cat_name = row.get('Category', '').strip()
                if not cat_name:
                    errors.append({'row': i, 'message': 'Category is required'})
                    continue
                category, _ = StockCategory.objects.get_or_create(
                    slug=slugify(cat_name), defaults={'name': cat_name}
                )

                unit = row.get('Unit', 'piece').strip().lower()
                if unit not in valid_units:
                    unit = 'piece'

                with transaction.atomic():
                    StockItem.objects.create(
                        name=name,
                        category=category,
                        sku=sku or '',
                        brand=row.get('Brand', '').strip(),
                        model_number=row.get('Model', '').strip(),
                        unit=unit,
                        quantity_in_stock=int(row.get('Quantity', 0) or 0),
                        minimum_stock_level=int(row.get('Min Level', 5) or 5),
                        purchase_price=row.get('Buy Price', 0) or 0,
                        selling_price=row.get('Sell Price', 0) or 0,
                    )
                    created += 1
            except Exception as e:
                errors.append({'row': i, 'message': str(e)})

        context['results'] = {'created': created, 'skipped': skipped, 'errors': errors}

    return render(request, 'common/csv_import.html', context)