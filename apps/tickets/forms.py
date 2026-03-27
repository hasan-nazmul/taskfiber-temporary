from django import forms
from .models import Ticket, TicketComment, TicketStockUsage
from apps.accounts.models import Employee, Team
from apps.customers.models import Customer, Area


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            'ticket_type', 'source', 'priority',
            'customer', 'contact_name', 'contact_phone', 'contact_address',
            'title', 'description',
            'assigned_team', 'assigned_to',
            'line_cut_reason',
            'work_location', 'area',
            'scheduled_date', 'scheduled_time_slot',
        ]
        widgets = {
            'source': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'contact_address': forms.Textarea(attrs={'rows': 2}),
            'work_location': forms.Textarea(attrs={'rows': 2}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(
            status__in=['active', 'suspended', 'pending']
        ).order_by('name')
        self.fields['customer'].required = False
        self.fields['assigned_to'].queryset = Employee.objects.filter(
            is_active=True
        ).exclude(
            role__slug__in=['owner', 'manager']
        ).select_related('user', 'role')
        self.fields['assigned_to'].required = False
        self.fields['area'].queryset = Area.objects.filter(is_active=True)


class TicketEditForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            'ticket_type', 'source', 'priority', 'status',
            'customer', 'contact_name', 'contact_phone', 'contact_address',
            'title', 'description',
            'assigned_team', 'assigned_to',
            'line_cut_reason',
            'work_location', 'area',
            'scheduled_date', 'scheduled_time_slot',
            'resolution_notes',
        ]
        widgets = {
            'source': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'contact_address': forms.Textarea(attrs={'rows': 2}),
            'work_location': forms.Textarea(attrs={'rows': 2}),
            'resolution_notes': forms.Textarea(attrs={'rows': 3}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.all().order_by('name')
        self.fields['customer'].required = False
        self.fields['assigned_to'].queryset = Employee.objects.filter(
            is_active=True
        ).exclude(
            role__slug__in=['owner', 'manager']
        ).select_related('user', 'role')
        self.fields['assigned_to'].required = False


class TicketAssignForm(forms.Form):
    assigned_team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        required=False
    )
    assigned_to = forms.ModelChoiceField(
        queryset=Employee.objects.filter(
            is_active=True
        ).exclude(
            role__slug__in=['owner', 'manager']
        ).select_related('user', 'role'),
        required=False
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


class TicketStatusForm(forms.Form):
    MANUAL_STATUS_CHOICES = [
        c for c in Ticket.STATUS_CHOICES if c[0] != 'assigned'
    ]
    status = forms.ChoiceField(choices=MANUAL_STATUS_CHOICES)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        help_text='Required when resolving a ticket'
    )


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['comment', 'is_internal']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Add a comment or note...'
            }),
        }


class TicketStockUsageForm(forms.ModelForm):
    class Meta:
        model = TicketStockUsage
        fields = ['stock_item', 'quantity_used', 'notes']
        widgets = {
            'notes': forms.TextInput(attrs={'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.stock.models import StockItem
        self.fields['stock_item'].queryset = StockItem.objects.filter(
            is_active=True, quantity_in_stock__gt=0
        )