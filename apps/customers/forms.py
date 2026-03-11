from django import forms
from .models import Customer, Area, Package


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'customer_id', 'name', 'phone', 'alt_phone', 'whatsapp_number',
            'email', 'nid_number',
            'area', 'address', 'gps_location',
            'package', 'connection_type', 'connection_date',
            'pppoe_username', 'ip_address', 'mac_address', 'onu_serial',
            'billing_date', 'monthly_amount',
            'status', 'last_payment_date', 'due_amount',
            'referred_by', 'notes',
        ]
        widgets = {
            'connection_date': forms.DateInput(attrs={'type': 'date'}),
            'last_payment_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer_id'].required = False
        self.fields['customer_id'].help_text = 'Leave blank for auto-generation'


class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['name', 'zone_code', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['name', 'bandwidth_mbps', 'price', 'package_type', 'is_active']