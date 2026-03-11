from django.db import models


class Area(models.Model):
    name = models.CharField(max_length=100)
    zone_code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.zone_code})"

    class Meta:
        ordering = ['name']


class Package(models.Model):
    PACKAGE_TYPE_CHOICES = [
        ('home', 'Home'),
        ('business', 'Business'),
        ('corporate', 'Corporate'),
    ]

    name = models.CharField(max_length=100)
    bandwidth_mbps = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    package_type = models.CharField(max_length=20, choices=PACKAGE_TYPE_CHOICES, default='home')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.bandwidth_mbps} Mbps) - ৳{self.price}"

    class Meta:
        ordering = ['bandwidth_mbps']


class Customer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Connection'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('disconnected', 'Disconnected'),
    ]

    CONNECTION_TYPE_CHOICES = [
        ('fiber', 'Fiber'),
        ('cable', 'Cable'),
        ('wireless', 'Wireless'),
    ]

    # Basic Info
    customer_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    alt_phone = models.CharField(max_length=15, blank=True, verbose_name='Alt Phone')
    whatsapp_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    nid_number = models.CharField(max_length=20, blank=True, verbose_name='NID Number')

    # Connection Info
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='customers')
    address = models.TextField()
    gps_location = models.CharField(max_length=100, blank=True,
                                     help_text='Latitude,Longitude')

    # Service Info
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name='customers')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='fiber')
    connection_date = models.DateField(null=True, blank=True)
    pppoe_username = models.CharField(max_length=50, blank=True, verbose_name='PPPoE Username')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    mac_address = models.CharField(max_length=17, blank=True, verbose_name='MAC Address')
    onu_serial = models.CharField(max_length=50, blank=True, verbose_name='ONU/Router Serial')

    # Billing
    billing_date = models.PositiveSmallIntegerField(default=1,
                                                      help_text='Day of month for billing')
    monthly_amount = models.DecimalField(max_digits=8, decimal_places=2)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Payment tracking (simple)
    last_payment_date = models.DateField(null=True, blank=True)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Metadata
    referred_by = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referred_customers'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_id} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last = Customer.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.customer_id = f"CUS-{num:05d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']