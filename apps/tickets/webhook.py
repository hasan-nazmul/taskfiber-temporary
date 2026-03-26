import json
import logging
import requests
import html
import re
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Ticket, TicketComment
from apps.accounts.models import Employee
from apps.schedule.models import Schedule

logger = logging.getLogger(__name__)

def send_telegram_message(chat_id, text, parse_mode='HTML', inline_keyboard=None):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if inline_keyboard:
        payload['reply_markup'] = {"inline_keyboard": inline_keyboard}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram message error: {e}")

def answer_callback_query(callback_id, text):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        requests.post(url, json={'callback_query_id': callback_id, 'text': text}, timeout=5)
    except Exception as e:
        logger.error(f"Telegram callback answer error: {e}")

def send_help(chat_id, employee):
    msg = (
        f"👋 Welcome, <b>{html.escape(employee.full_name)}</b>!\n\n"
        "Here are your quick commands:\n"
        "🔹 /tasks - View all your active tickets\n"
        "🔹 /schedule - View your assigned schedule for the week\n"
        "🔹 /ticket [ID] - View full details of a specific ticket\n\n"
        "💡 <b>Pro Tip:</b> You can instantly add a comment to a ticket by "
        "simply <i>Swiping to Reply</i> to any ticket notification I send you!"
    )
    send_telegram_message(chat_id, msg)

def send_tasks_list(chat_id, employee):
    tickets = Ticket.objects.filter(
        assigned_to=employee,
        status__in=['open', 'assigned', 'in_progress']
    ).order_by('-priority', '-created_at')
    
    if not tickets.exists():
        send_telegram_message(chat_id, "✅ You have no active tasks currently.")
        return
        
    msg = f"📋 <b>Your Active Tasks ({tickets.count()}):</b>\n\n"
    for idx, t in enumerate(tickets, 1):
        customer_name = t.customer.name if t.customer else t.contact_name
        safe_customer = html.escape(str(customer_name or 'N/A'))
        msg += f"<b>{idx}.</b> /ticket_{t.id} (Ref: <b>{t.ticket_number}</b>)\n"
        msg += f"   👤 {safe_customer}\n"
        msg += f"   📌 {t.get_status_display()}\n\n"
        
    send_telegram_message(chat_id, msg)

def send_schedule(chat_id, employee):
    today = timezone.now().date()
    end_date = today + timedelta(days=7)
    schedules = Schedule.objects.filter(
        employee=employee,
        date__gte=today,
        date__lte=end_date
    ).order_by('date')

    if not schedules.exists():
        send_telegram_message(chat_id, "📅 You have no scheduled shifts for the next 7 days.")
        return

    msg = "📅 <b>Your Schedule (Next 7 Days):</b>\n\n"
    for s in schedules:
        day_str = s.date.strftime("%a, %b %d")
        if s.date == today:
            day_str = "<b>Today</b>"
        
        area_str = s.assigned_area.name if s.assigned_area else "Any"
        msg += f"• {day_str}: <b>{s.get_shift_display()}</b> (Area: {area_str})\n"
        
    send_telegram_message(chat_id, msg)

def send_ticket_detail(chat_id, employee, ticket_ref):
    # Support both /ticket_123 and /ticket TKT-2026...
    ticket_ref = ticket_ref.replace('/ticket_', '').strip()
    try:
        if ticket_ref.isdigit():
            ticket = Ticket.objects.get(id=ticket_ref, assigned_to=employee)
        else:
            ticket = Ticket.objects.get(ticket_number=ticket_ref, assigned_to=employee)
    except Ticket.DoesNotExist:
        send_telegram_message(chat_id, f"❌ Ticket `{ticket_ref}` not found or not assigned to you.")
        return

    customer_name = ticket.customer.name if ticket.customer else ticket.contact_name
    address = ticket.customer.address if ticket.customer else ticket.contact_address
    
    msg = f"🔍 <b>Ticket Details: {ticket.ticket_number}</b>\n\n"
    msg += f"<b>Status:</b> {ticket.get_status_display()}\n"
    msg += f"<b>Priority:</b> {ticket.get_priority_display()}\n"
    msg += f"<b>Customer:</b> {html.escape(str(customer_name or 'N/A'))}\n"
    msg += f"<b>Phone:</b> {ticket.customer.phone if ticket.customer else ticket.contact_phone}\n"
    msg += f"<b>Address:</b> {html.escape(str(address or 'N/A'))}\n"
    msg += f"<b>Issue:</b> {html.escape(str(ticket.title))}\n"
    if ticket.description:
        msg += f"\n<i>{html.escape(str(ticket.description))}</i>\n"

    # Inline Buttons
    buttons = [
        [
            {"text": "🚀 Accept (In Progress)", "callback_data": f"accept_{ticket.id}"},
            {"text": "✅ Mark Resolved", "callback_data": f"resolve_{ticket.id}"}
        ]
    ]
    send_telegram_message(chat_id, msg, inline_keyboard=buttons)

def add_comment_to_ticket(chat_id, employee, ticket_ref, comment_text):
    try:
        if ticket_ref.startswith('TKT-'):
            ticket = Ticket.objects.get(ticket_number=ticket_ref)
        else:
            ticket = Ticket.objects.get(id=ticket_ref)
            
        TicketComment.objects.create(
            ticket=ticket,
            author=employee,
            comment=comment_text,
            is_internal=True
        )
        send_telegram_message(chat_id, f"💬 Comment saved to ticket <b>{ticket.ticket_number}</b> successfully!")
    except Ticket.DoesNotExist:
        send_telegram_message(chat_id, "⚠️ Could not identify the ticket to attach this comment to.")


def handle_message(chat_id, text, message_obj):
    try:
        employee = Employee.objects.get(telegram_chat_id=str(chat_id))
    except Employee.DoesNotExist:
        send_telegram_message(chat_id, "❌ Sorry, this Telegram account is not linked to any Employee profile.")
        return

    text = text.strip()
    
    # Force ticket deep link commands: /ticket_123
    if text.startswith('/ticket_'):
        send_ticket_detail(chat_id, employee, text)
        return

    commands = text.split()
    cmd = commands[0].lower() if commands else ''

    if cmd in ['/start', '/help']:
        send_help(chat_id, employee)
    elif cmd == '/tasks':
        send_tasks_list(chat_id, employee)
    elif cmd == '/schedule':
        send_schedule(chat_id, employee)
    elif cmd == '/ticket':
        if len(commands) > 1:
            send_ticket_detail(chat_id, employee, commands[1])
        else:
            send_telegram_message(chat_id, "Please provide a ticket ID, e.g., `/ticket 123`")
            
    elif cmd == '/comment':
        if len(commands) > 2:
            ticket_id = commands[1]
            comment_body = text.split(" ", 2)[2]  # Everything after "/comment 123 "
            add_comment_to_ticket(chat_id, employee, ticket_id, comment_body)
        else:
            send_telegram_message(chat_id, "Please provide the ticket ID and your comment, e.g., `/comment 123 Customer is not home.`")
            
    # Check if this is a "Reply" to a previous bot message
    elif 'reply_to_message' in message_obj:
        parent_text = message_obj['reply_to_message'].get('text', '')
        # Try to find ticket number TKT-YYYYMMDD-SEQ
        match = re.search(r'TKT-\d{8}-\d{3}', parent_text)
        if not match:
            # Fallback: find Ticket #ID
            match = re.search(r'Ticket #:\s*(\w+)', parent_text) or re.search(r'Ticket Details:\s*(\w+)', parent_text)
            
        if match:
            ticket_ref = match.group(0)
            if 'Ticket' in ticket_ref: 
                ticket_ref = match.group(1) # Extract just the matched group
            add_comment_to_ticket(chat_id, employee, ticket_ref, text)
        else:
            send_telegram_message(chat_id, "⚠️ I couldn't find a Ticket ID in the message you replied to.")
    else:
        # Fallback if they write random text
        send_help(chat_id, employee)


def handle_callback(chat_id, data, callback_id):
    try:
        employee = Employee.objects.get(telegram_chat_id=str(chat_id))
    except Employee.DoesNotExist:
        answer_callback_query(callback_id, "Unauthorized User!")
        return

    if data.startswith('accept_') or data.startswith('resolve_'):
        action, ticket_id = data.split('_', 1)
        try:
            ticket = Ticket.objects.get(id=ticket_id, assigned_to=employee)
            if ticket.status in ['resolved', 'closed', 'cancelled']:
                answer_callback_query(callback_id, "Ticket is already closed!")
            else:
                if action == 'accept':
                    ticket.status = 'in_progress'
                    ticket._skip_telegram = True
                    ticket.save(update_fields=['status'])
                    answer_callback_query(callback_id, "✅ Ticket Accepted!")
                    send_telegram_message(chat_id, f"🚀 You accepted Ticket <b>{ticket.ticket_number}</b>.")
                elif action == 'resolve':
                    ticket.status = 'resolved'
                    ticket.resolved_at = timezone.now()
                    ticket.resolved_by = employee
                    ticket._skip_telegram = True
                    ticket.save(update_fields=['status', 'resolved_at', 'resolved_by'])
                    answer_callback_query(callback_id, "✅ Ticket Resolved!")
                    send_telegram_message(chat_id, f"🎉 Great job! Ticket <b>{ticket.ticket_number}</b> resolved.")
        except Ticket.DoesNotExist:
            answer_callback_query(callback_id, "Ticket Not Found!")


@csrf_exempt
def telegram_webhook(request, token):
    if token != getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    if request.method == 'POST':
        try:
            update = json.loads(request.body)
            if 'message' in update:
                message = update['message']
                chat_id = message.get('chat', {}).get('id')
                text = (message.get('text') or message.get('caption') or '').strip()
                if chat_id and text:
                    handle_message(chat_id, text, message)
                    
            elif 'callback_query' in update:
                callback = update['callback_query']
                chat_id = callback.get('message', {}).get('chat', {}).get('id')
                data = callback.get('data', '')
                callback_id = callback.get('id')
                if chat_id and data and callback_id:
                    handle_callback(chat_id, data, callback_id)
                    
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            logger.error(f"Telegram Webhook Error: {e}")
            return JsonResponse({'status': 'error'}, status=500)
            
    return JsonResponse({'status': 'invalid method'}, status=405)
