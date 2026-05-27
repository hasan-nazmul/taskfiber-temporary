"""
message_handler.py — Conversation flow logic for the WhatsApp bot.

This module implements the core "No-UI" MVP workflow:

  Hi / Menu  →  [📋 My Tasks]  [🚨 Report Issue]
  My Tasks   →  ticket list + [✅ Mark Done] per ticket
  Mark Done  →  update DB, send confirmation
"""

import logging
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Employee
from apps.tickets.models import Ticket, TicketStatusLog
from .whatsapp_api import send_text_message, send_button_message

logger = logging.getLogger('whatsapp_bot')

# ─── Status mapping ─────────────────────────────────────────────────────────
# The existing Ticket model has 8 statuses. For the WhatsApp MVP we collapse
# them into three buckets so field staff see a simple view.
#
#   NEW         = open, assigned
#   IN_PROGRESS = in_progress, waiting_customer, waiting_payment
#   DONE        = resolved, closed, cancelled
#
ACTIVE_STATUSES = ['open', 'assigned', 'in_progress', 'waiting_customer', 'waiting_payment']


def _normalize_phone(raw_phone: str) -> str:
    """
    Normalize a phone number from WhatsApp format to our DB format.

    WhatsApp sends numbers WITHOUT the '+' prefix (e.g. "8801712345678").
    Our Employee model stores them WITH the '+' prefix (e.g. "+8801712345678").
    """
    phone = raw_phone.strip()
    if not phone.startswith('+'):
        phone = f'+{phone}'
    return phone


def _lookup_employee(sender_phone: str) -> Employee | None:
    """
    Find an active Employee by their phone number.
    Checks whatsapp_number first, then falls back to the primary phone field.
    """
    phone = _normalize_phone(sender_phone)

    try:
        return Employee.objects.get(
            Q(whatsapp_number=phone) | Q(phone=phone),
            is_active=True,
        )
    except Employee.DoesNotExist:
        return None
    except Employee.MultipleObjectsReturned:
        # Edge case: same number in both fields of different employees.
        # Return the one where whatsapp_number matches explicitly.
        return Employee.objects.filter(
            whatsapp_number=phone, is_active=True
        ).first()


# ─── Flow handlers ───────────────────────────────────────────────────────────

def handle_menu(sender: str, employee: Employee):
    """Send the main menu with two action buttons."""
    body = (
        f"👋 Hello, *{employee.full_name}*!\n\n"
        "What would you like to do?"
    )
    buttons = [
        {'id': 'my_tasks',     'title': '📋 My Tasks'},
        {'id': 'report_issue', 'title': '🚨 Report Issue'},
    ]
    send_button_message(sender, body, buttons)


def handle_my_tasks(sender: str, employee: Employee):
    """Query active tickets for this employee and send a formatted list."""
    tickets = Ticket.objects.filter(
        assigned_to=employee,
        status__in=ACTIVE_STATUSES,
    ).order_by('-priority', '-created_at')

    if not tickets.exists():
        send_text_message(sender, '✅ You have no active tasks right now. Great job!')
        return

    # Build the task list text
    lines = [f'📋 *Your Active Tasks ({tickets.count()}):*\n']
    for idx, ticket in enumerate(tickets, 1):
        customer = ticket.customer.name if ticket.customer else ticket.contact_name or 'N/A'
        status_label = _status_label(ticket.status)
        lines.append(
            f'{idx}. [{status_label}] {ticket.title}\n'
            f'   👤 {customer}\n'
            f'   🔖 {ticket.ticket_number}'
        )

    # WhatsApp interactive buttons are limited to 3, so if there are more than
    # 3 active tickets we show a "Mark Done" only for the top 3 (highest priority).
    task_buttons = [
        {
            'id': f'done_{ticket.id}',
            'title': f'✅ Done #{ticket.ticket_number[-3:]}',  # last 3 chars of ticket #
        }
        for ticket in tickets[:3]
    ]

    body = '\n'.join(lines)

    if task_buttons:
        send_button_message(sender, body, task_buttons)
    else:
        send_text_message(sender, body)


def handle_mark_done(sender: str, employee: Employee, ticket_id: str):
    """Mark a ticket as resolved."""
    try:
        ticket = Ticket.objects.get(id=ticket_id, assigned_to=employee)
    except Ticket.DoesNotExist:
        send_text_message(sender, '❌ Ticket not found or not assigned to you.')
        return

    if ticket.status in ['resolved', 'closed', 'cancelled']:
        send_text_message(sender, f'ℹ️ Ticket *{ticket.ticket_number}* is already done.')
        return

    old_status = ticket.status

    # Update the ticket
    ticket.status = 'resolved'
    ticket.resolved_at = timezone.now()
    ticket.resolved_by = employee
    # Prevent the Telegram signal from double-notifying
    ticket._skip_telegram = True
    ticket.save(update_fields=['status', 'resolved_at', 'resolved_by'])

    # Log the status change
    TicketStatusLog.objects.create(
        ticket=ticket,
        old_status=old_status,
        new_status='resolved',
        changed_by=employee,
        notes='Marked as done via WhatsApp bot.',
    )

    send_text_message(
        sender,
        f'🎉 *Done!* Ticket *{ticket.ticket_number}* has been marked as resolved.\n\n'
        f'Send "Menu" to go back to the main menu.'
    )
    logger.info(
        'Ticket %s resolved via WhatsApp by %s',
        ticket.ticket_number, employee.full_name,
    )


def handle_report_issue(sender: str, employee: Employee):
    """
    MVP stub for issue reporting.
    For now, instruct the user to describe the issue. A future iteration
    will capture the next message and create a Ticket automatically.
    """
    send_text_message(
        sender,
        '🚨 *Report an Issue*\n\n'
        'Please describe the issue in your next message and a manager will '
        'be notified to create a ticket for you.\n\n'
        '_(Automatic ticket creation coming soon!)_'
    )


# ─── Main dispatcher ─────────────────────────────────────────────────────────

def process_incoming_message(sender_phone: str, message_body: str,
                              button_payload: str | None = None):
    """
    Main entry point called from the webhook view.

    Args:
        sender_phone:   The WhatsApp sender number (e.g. "8801712345678")
        message_body:   The text body (for regular text messages)
        button_payload: The button reply ID (for interactive button responses)
    """
    employee = _lookup_employee(sender_phone)

    if employee is None:
        send_text_message(
            _normalize_phone(sender_phone),
            '⛔ Unauthorized. Your phone number is not registered in the system.\n'
            'Please contact your manager.',
        )
        logger.warning('Unauthorized WhatsApp access attempt from %s', sender_phone)
        return

    sender = _normalize_phone(sender_phone)

    # ── Handle interactive button callbacks ──────────────────────────────
    if button_payload:
        if button_payload == 'my_tasks':
            handle_my_tasks(sender, employee)
        elif button_payload == 'report_issue':
            handle_report_issue(sender, employee)
        elif button_payload.startswith('done_'):
            ticket_id = button_payload.removeprefix('done_')
            handle_mark_done(sender, employee, ticket_id)
        else:
            # Unknown button — show menu
            handle_menu(sender, employee)
        return

    # ── Handle free-text messages ────────────────────────────────────────
    text = message_body.strip().lower()

    if text in ('hi', 'hello', 'menu', 'start', 'hey', '/start'):
        handle_menu(sender, employee)
    elif text in ('tasks', 'my tasks', '/tasks'):
        handle_my_tasks(sender, employee)
    else:
        # Default: show menu for any unrecognized text
        handle_menu(sender, employee)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _status_label(status: str) -> str:
    """Map a DB status value to a human-readable emoji label."""
    mapping = {
        'open': '🆕 NEW',
        'assigned': '🆕 NEW',
        'in_progress': '🔄 IN PROGRESS',
        'waiting_customer': '🔄 IN PROGRESS',
        'waiting_payment': '🔄 IN PROGRESS',
        'resolved': '✅ DONE',
        'closed': '✅ DONE',
        'cancelled': '✅ DONE',
    }
    return mapping.get(status, status.upper())
