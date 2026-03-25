import logging
import requests
import html
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Ticket

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Ticket)
def send_telegram_notification(sender, instance, created, **kwargs):
    # Skip if we deliberately asked it to avoid looping
    if getattr(instance, '_skip_telegram', False):
        return

    # Condition 1: Only send if ticket has an assigned employee AND that employee has a telegram_chat_id
    if not instance.assigned_to:
        return
        
    chat_id = instance.assigned_to.telegram_chat_id
    if not chat_id:
        return

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured in settings.")
        return

    # Condition 2: Differentiate between a newly created ticket and an updated ticket
    if created:
        header = "🚨 <b>NEW TICKET ASSIGNED</b> 🚨"
    else:
        header = "🔄 <b>TICKET UPDATED</b> 🔄"

    # Get dynamic values handling potential nulls
    customer_name = instance.customer.name if instance.customer else instance.contact_name
    address = instance.customer.address if instance.customer else instance.contact_address
    issue = instance.title
    priority_display = instance.get_priority_display()

    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    
    # Message Formatting using HTML (Much safer than Markdown for dynamic user input)
    safe_customer = html.escape(str(customer_name or 'N/A'))
    safe_address = html.escape(str(address or 'N/A'))
    safe_issue = html.escape(str(issue or 'N/A'))
    
    message = f"{header}\n\n"
    message += f"<b>Ticket #:</b> {instance.ticket_number}\n"
    message += f"<b>Customer:</b> {safe_customer}\n"
    message += f"<b>Issue:</b> {safe_issue}\n"
    message += f"<b>Address:</b> {safe_address}\n"
    message += f"<b>Priority:</b> {priority_display}\n\n"
    message += f"🌐 <a href=\"{site_url}/tickets/{instance.id}/\">Click here to open ticket</a>"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Accept (In Progress)", "callback_data": f"accept_{instance.id}"},
                {"text": "✅ Mark as Resolved", "callback_data": f"resolve_{instance.id}"}
            ]
        ]
    }
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'reply_markup': inline_keyboard
    }

    # Wrap the request in a try/except block
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram notification (Chat: {chat_id}) for ticket {instance.ticket_number}. Error: {str(e)}")
        # If it fails, log the response text if available for easier debugging
        if hasattr(e, 'response') and e.response is not None:
             logger.error(f"Telegram API Response: {e.response.text}")
