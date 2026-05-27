"""
views.py — WhatsApp webhook endpoint for Meta Cloud API.

This view handles two request types:

  GET  — Meta's one-time webhook verification (token challenge).
  POST — Incoming messages and interactive button responses from WhatsApp users.

Webhook URL to register with Meta:
    https://<your-render-domain>/whatsapp/webhook/

Required environment variables (set in Render dashboard or .env):
    WHATSAPP_VERIFY_TOKEN  — a random secret string you choose, must match Meta's config
    WHATSAPP_ACCESS_TOKEN  — your Meta Cloud API access token
    WHATSAPP_PHONE_ID      — the Phone Number ID from Meta API Setup
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .message_handler import process_incoming_message

logger = logging.getLogger('whatsapp_bot')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request):
    """
    Single endpoint that handles both Meta's verification challenge (GET)
    and incoming webhook events (POST).
    """
    if request.method == 'GET':
        return _handle_verification(request)
    else:
        return _handle_incoming(request)


# ─── GET: Webhook Verification ──────────────────────────────────────────────

def _handle_verification(request):
    """
    Meta sends a GET request when you first register the webhook URL.
    It includes three query params:
      - hub.mode          = "subscribe"
      - hub.verify_token  = the token you configured in Meta dashboard
      - hub.challenge     = a random string Meta expects you to echo back

    If the verify_token matches, echo the challenge with 200.
    Otherwise, return 403.
    """
    mode = request.GET.get('hub.mode', '')
    token = request.GET.get('hub.verify_token', '')
    challenge = request.GET.get('hub.challenge', '')

    expected_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == 'subscribe' and token == expected_token:
        logger.info('WhatsApp webhook verified successfully.')
        return HttpResponse(challenge, content_type='text/plain', status=200)

    logger.warning('WhatsApp webhook verification failed. Token mismatch.')
    return HttpResponse('Forbidden', status=403)


# ─── POST: Incoming Messages ────────────────────────────────────────────────

def _handle_incoming(request):
    """
    Parse the Cloud API webhook payload and dispatch to the message handler.

    Payload structure (simplified):
    {
      "entry": [{
        "changes": [{
          "value": {
            "messages": [{
              "from": "8801712345678",
              "type": "text" | "interactive",
              "text": {"body": "Hi"},                           // for type=text
              "interactive": {"button_reply": {"id": "my_tasks"}} // for type=interactive
            }]
          }
        }]
      }]
    }

    We always return 200 quickly to avoid Meta retrying the webhook.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.error('Invalid JSON in WhatsApp webhook request.')
        return JsonResponse({'status': 'error', 'detail': 'Invalid JSON'}, status=400)

    # Traverse the nested payload safely
    entries = body.get('entry', [])
    for entry in entries:
        changes = entry.get('changes', [])
        for change in changes:
            value = change.get('value', {})
            messages = value.get('messages', [])

            for message in messages:
                _dispatch_message(message)

    # Always return 200 to acknowledge receipt; Meta will retry on non-2xx.
    return JsonResponse({'status': 'ok'})


def _dispatch_message(message: dict):
    """
    Extract sender phone, message content, and button payload from a single
    message object, then hand off to the conversation flow handler.
    """
    sender = message.get('from', '')
    msg_type = message.get('type', '')

    if not sender:
        return

    message_body = ''
    button_payload = None

    if msg_type == 'text':
        message_body = message.get('text', {}).get('body', '')

    elif msg_type == 'interactive':
        # Interactive button reply
        interactive = message.get('interactive', {})
        interactive_type = interactive.get('type', '')

        if interactive_type == 'button_reply':
            button_reply = interactive.get('button_reply', {})
            button_payload = button_reply.get('id', '')
            message_body = button_reply.get('title', '')

        elif interactive_type == 'list_reply':
            list_reply = interactive.get('list_reply', {})
            button_payload = list_reply.get('id', '')
            message_body = list_reply.get('title', '')

    else:
        # Unsupported message type (image, audio, etc.) — ignore for MVP
        logger.debug('Ignoring unsupported message type: %s', msg_type)
        return

    if message_body or button_payload:
        try:
            process_incoming_message(sender, message_body, button_payload)
        except Exception:
            logger.exception(
                'Error processing WhatsApp message from %s', sender
            )
