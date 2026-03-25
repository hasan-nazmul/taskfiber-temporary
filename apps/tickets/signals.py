import logging
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Ticket

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Ticket)
def send_telegram_notification(sender, instance, created, **kwargs):
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
        header = "🚨 *NEW TICKET ASSIGNED* 🚨"
    else:
        header = "🔄 *TICKET UPDATED* 🔄"

    # Get dynamic values handling potential nulls
    customer_name = instance.customer.name if instance.customer else instance.contact_name
    address = instance.customer.address if instance.customer else instance.contact_address
    issue = instance.title
    priority_display = instance.get_priority_display()

    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    
    # Message Formatting (Markdown) blending the requested elements
    message = f"{header}\n\n"
    message += f"*Ticket #:* {instance.ticket_number}\n"
    message += f"*Customer:* {customer_name}\n"
    message += f"*Issue:* {issue}\n"
    message += f"*Address:* {address}\n"
    message += f"*Priority:* {priority_display}\n\n"
    message += f"🌐 [Click here to open ticket]({site_url}/tickets/{instance.id}/)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }

    # Wrap the request in a try/except block with timeout as requested
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram notification for ticket {instance.ticket_number}: {str(e)}")
