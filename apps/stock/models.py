from django.db import models


class StockCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Stock Categories'
        ordering = ['name']


class StockItem(models.Model):
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('meter', 'Meter'),
        ('roll', 'Roll'),
        ('box', 'Box'),
        ('set', 'Set'),
    ]

    category = models.ForeignKey(StockCategory, on_delete=models.PROTECT, related_name='items')
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True, blank=True, verbose_name='SKU')
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)

    # Quantity
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')
    quantity_in_stock = models.PositiveIntegerField(default=0)
    minimum_stock_level = models.PositiveIntegerField(default=5)

    # Pricing
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Location
    warehouse_location = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.quantity_in_stock} {self.get_unit_display()})"

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.minimum_stock_level

    @property
    def stock_value(self):
        return self.quantity_in_stock * self.purchase_price

    def save(self, *args, **kwargs):
        if not self.sku:
            prefix = self.category.slug[:3].upper() if self.category else 'STK'
            last = StockItem.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.sku = f"{prefix}-{num:04d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['category', 'name']


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('purchase', 'Purchase/Restock'),
        ('issue', 'Issued to Technician'),
        ('used', 'Used on Ticket'),
        ('return', 'Returned'),
        ('damaged', 'Damaged/Write-off'),
        ('adjustment', 'Manual Adjustment'),
    ]

    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField(help_text='Positive for stock in, negative for stock out')

    # References
    ticket = models.ForeignKey(
        'tickets.Ticket', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_transactions'
    )
    issued_to = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_issued'
    )

    # Purchase details
    vendor_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=50, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT,
        related_name='stock_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        direction = "IN" if self.quantity > 0 else "OUT"
        return f"{direction} {abs(self.quantity)} x {self.stock_item.name} ({self.get_transaction_type_display()})"

    @property
    def total_cost(self):
        return abs(self.quantity) * self.unit_price

    class Meta:
        ordering = ['-created_at']