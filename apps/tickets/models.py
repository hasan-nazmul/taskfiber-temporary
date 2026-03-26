from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    # Grouped Choices for specialized team routing
    TICKET_TYPE_CHOICES = [
        ('Cable Team (Physical Layer)', (
            ('line_cut', 'Fiber Cut / ONU Red Light'),
            ('olt_down', 'OLT Down'),
            ('mikrotik_down', 'MikroTik Down'),
            ('line_shift', 'Line Shift'),
            ('new_connection', 'New Line (Connection)'),
            ('db_issue', 'DB Issue'),
            ('pon_fluctuation', 'PON Fluctuation'),
            ('adapter_issue', 'Adapter Issue (Field)'),
        )),
        ('Support Team (Logical Layer)', (
            ('router_setup', 'Router Setup'),
            ('speed_slow', 'Speed Issue'),
            ('password_change', 'Password Change'),
            ('tv_connect', 'TV Connect'),
            ('area_coverage', 'Area Coverage Inquiry'),
            ('support_other', 'Other Support'),
        )),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting on Customer'),
        ('waiting_payment', 'Waiting on Payment'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]

    SOURCE_CHOICES = [
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('walk_in', 'Walk-in'),
        ('marketing', 'Marketing Team'),
        ('self', 'Self Identified'),
    ]

    LINE_CUT_REASON_CHOICES = [
        ('pay_off', 'Payment Due/Off'),
        ('pay_not_received', 'Payment Not Received'),
        ('technical', 'Technical Problem'),
        ('cable_damage', 'Cable Damage'),
        ('other', 'Other'),
    ]

    # Ticket Identity
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    ticket_type = models.CharField(max_length=30, choices=TICKET_TYPE_CHOICES)

    # Who raised it
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='phone')
    created_by = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT,
        related_name='tickets_created'
    )

    # Customer
    customer = models.ForeignKey(
        'customers.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tickets'
    )
    # For new customers not yet in system
    contact_name = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    contact_address = models.TextField(blank=True)

    # Ticket details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # Assignment
    assigned_team = models.ForeignKey(
        'accounts.Team', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_tickets'
    )
    assigned_to = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tickets_assigned'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    # Line Cut specific
    line_cut_reason = models.CharField(
        max_length=30, choices=LINE_CUT_REASON_CHOICES, blank=True
    )

    # Location for field work
    work_location = models.TextField(blank=True)
    area = models.ForeignKey(
        'customers.Area', null=True, blank=True,
        on_delete=models.SET_NULL
    )

    # Resolution
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'accounts.Employee', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tickets_resolved'
    )

    # Schedule
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time_slot = models.CharField(max_length=20, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ticket_number} - {self.get_ticket_type_display()}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            today = timezone.now().strftime('%Y%m%d')
            last = Ticket.objects.filter(
                ticket_number__startswith=f'TKT-{today}'
            ).order_by('-ticket_number').first()

            if last:
                last_seq = int(last.ticket_number.split('-')[-1])
                seq = last_seq + 1
            else:
                seq = 1

            self.ticket_number = f'TKT-{today}-{seq:03d}'

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['ticket_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['assigned_to', 'status']),
        ]


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT
    )
    comment = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment on {self.ticket.ticket_number} by {self.author}"

    class Meta:
        ordering = ['-created_at']


class TicketStatusLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticket.ticket_number}: {self.old_status} → {self.new_status}"

    class Meta:
        ordering = ['-created_at']


class TicketStockUsage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='stock_used')
    stock_item = models.ForeignKey(
        'stock.StockItem', on_delete=models.PROTECT
    )
    quantity_used = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=200, blank=True)
    added_by = models.ForeignKey(
        'accounts.Employee', on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.stock_item.name} x{self.quantity_used} on {self.ticket.ticket_number}"

    class Meta:
        ordering = ['-created_at']