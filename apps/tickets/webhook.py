import json
import logging
import requests
import html
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Ticket
from apps.accounts.models import Employee

logger = logging.getLogger(__name__)

def send_telegram_message(chat_id, text, parse_mode='HTML'):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram webhook reply error: {e}")

def answer_callback_query(callback_id, text):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        requests.post(url, json={'callback_query_id': callback_id, 'text': text}, timeout=5)
    except Exception as e:
        logger.error(f"Telegram callback answer error: {e}")

def send_tasks_list(chat_id):
    try:
        employee = Employee.objects.get(telegram_chat_id=str(chat_id))
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
            safe_issue = html.escape(str(t.title or 'N/A'))
            
            msg += f"{idx}. <b>#{t.ticket_number}</b> - {safe_customer}\n"
            msg += f"   Issue: {safe_issue}\n"
            msg += f"   Status: {t.get_status_display()}\n\n"
            
        send_telegram_message(chat_id, msg)
    except Employee.DoesNotExist:
        send_telegram_message(chat_id, "❌ Sorry, this Telegram account is not linked to any Employee profile.")

def handle_callback(chat_id, data, callback_id):
    try:
        employee = Employee.objects.get(telegram_chat_id=str(chat_id))
    except Employee.DoesNotExist:
        answer_callback_query(callback_id, "Unauthorized User!")
        return

    if data.startswith('accept_'):
        ticket_id = data.replace('accept_', '')
        try:
            ticket = Ticket.objects.get(id=ticket_id, assigned_to=employee)
            if ticket.status in ['resolved', 'closed', 'cancelled']:
                answer_callback_query(callback_id, "Ticket is already closed!")
            else:
                ticket.status = 'in_progress'
                ticket._skip_telegram = True
                ticket.save(update_fields=['status'])
                answer_callback_query(callback_id, "✅ Ticket Accepted!")
                send_telegram_message(chat_id, f"🚀 You accepted Ticket <b>#{ticket.ticket_number}</b>. Status updated to 'In Progress'.")
        except Ticket.DoesNotExist:
            answer_callback_query(callback_id, "Ticket Not Found!")

    elif data.startswith('resolve_'):
        ticket_id = data.replace('resolve_', '')
        try:
            ticket = Ticket.objects.get(id=ticket_id, assigned_to=employee)
            if ticket.status in ['resolved', 'closed', 'cancelled']:
                answer_callback_query(callback_id, "Ticket is already resolved!")
            else:
                ticket.status = 'resolved'
                ticket.resolved_at = timezone.now()
                ticket.resolved_by = employee
                ticket._skip_telegram = True
                ticket.save(update_fields=['status', 'resolved_at', 'resolved_by'])
                answer_callback_query(callback_id, "✅ Ticket Resolved!")
                send_telegram_message(chat_id, f"🎉 Great job! Ticket <b>#{ticket.ticket_number}</b> marked as Resolved.")
        except Ticket.DoesNotExist:
            answer_callback_query(callback_id, "Ticket Not Found!")

@csrf_exempt
def telegram_webhook(request, token):
    if token != getattr(settings, 'TELEGRAM_BOT_TOKEN', ''):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    if request.method == 'POST':
        try:
            update = json.loads(request.body)
            # Route to either a message or a callback query
            if 'message' in update:
                message = update['message']
                chat_id = message.get('chat', {}).get('id')
                text = message.get('text', '').strip()
                if text.startswith('/tasks'):
                    send_tasks_list(chat_id)
                    
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
