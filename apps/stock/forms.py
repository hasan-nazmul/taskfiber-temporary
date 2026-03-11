from django import forms
from .models import StockCategory, StockItem, StockTransaction
from apps.accounts.models import Employee


class StockCategoryForm(forms.ModelForm):
    class Meta:
        model = StockCategory
        fields = ['name', 'slug', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class StockItemForm(forms.ModelForm):
    class Meta:
        model = StockItem
        fields = [
            'category', 'name', 'sku', 'brand', 'model_number',
            'unit', 'quantity_in_stock', 'minimum_stock_level',
            'purchase_price', 'selling_price',
            'warehouse_location', 'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sku'].required = False
        self.fields['sku'].help_text = 'Leave blank for auto-generation'


class StockPurchaseForm(forms.Form):
    """Form for purchasing/restocking items"""
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.filter(is_active=True),
        label='Item'
    )
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    unit_price = forms.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, label='Unit Price'
    )
    vendor_name = forms.CharField(max_length=200, required=False)
    invoice_number = forms.CharField(max_length=50, required=False)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )


class StockIssueForm(forms.Form):
    """Form for issuing stock to technician"""
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.filter(is_active=True, quantity_in_stock__gt=0),
        label='Item'
    )
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    issued_to = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True).select_related('user'),
        label='Issue To'
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )


class StockReturnForm(forms.Form):
    """Form for returning stock"""
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.filter(is_active=True),
        label='Item'
    )
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    returned_by = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True).select_related('user'),
        label='Returned By',
        required=False
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )


class StockAdjustmentForm(forms.Form):
    """Form for manual stock adjustment"""
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.filter(is_active=True),
        label='Item'
    )
    adjustment_type = forms.ChoiceField(choices=[
        ('add', 'Add to Stock'),
        ('remove', 'Remove from Stock'),
    ])
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label='Reason'
    )