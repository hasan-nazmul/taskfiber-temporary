from django.contrib import admin
from .models import Ticket, TicketComment, TicketStatusLog, TicketStockUsage


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0


class TicketStatusLogInline(admin.TabularInline):
    model = TicketStatusLog
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'created_at']


class TicketStockUsageInline(admin.TabularInline):
    model = TicketStockUsage
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'ticket_type', 'customer', 'status',
        'priority', 'assigned_to', 'created_at'
    ]
    list_filter = ['status', 'ticket_type', 'priority', 'assigned_team', 'created_at']
    search_fields = [
        'ticket_number', 'title', 'customer__name',
        'contact_name', 'contact_phone'
    ]
    inlines = [TicketCommentInline, TicketStatusLogInline, TicketStockUsageInline]


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'author', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at']