"""
whatsapp_api.py — Helper functions for Meta's WhatsApp Cloud API.

These functions build the correct JSON payloads and POST them to the
Graph API endpoint. All secrets are read from django.conf.settings:

    WHATSAPP_ACCESS_TOKEN  — Your temporary/permanent access token from Meta
    WHATSAPP_PHONE_ID      — The Phone Number ID (from API Setup, NOT the phone number itself)

Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger('whatsapp_bot')

# ─── Meta Graph API base URL ────────────────────────────────────────────────
GRAPH_API_VERSION = 'v21.0'


def _get_api_url():
    """Build the messages endpoint URL from the configured Phone Number ID."""
    phone_id = settings.WHATSAPP_PHONE_ID
    return f'https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages'


def _get_headers():
    """Authorization headers for the Cloud API."""
    return {
        'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }


def _post_to_whatsapp(payload: dict) -> dict | None:
    """
    Send a payload to the WhatsApp Cloud API.
    Returns the parsed JSON response on success, None on failure.
    """
    url = _get_api_url()
    headers = _get_headers()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.debug('WhatsApp API response: %s', data)
        return data
    except requests.RequestException as exc:
        logger.error('WhatsApp API error: %s', exc)
        if hasattr(exc, 'response') and exc.response is not None:
            logger.error('Response body: %s', exc.response.text)
        return None


# ─── Public helpers ──────────────────────────────────────────────────────────

def send_text_message(to: str, body: str) -> dict | None:
    """
    Send a plain text message to a WhatsApp number.

    Args:
        to:   Recipient phone number in international format (e.g. "+8801712345678")
        body: The message text (max 4096 chars)
    """
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'text',
        'text': {'body': body},
    }
    return _post_to_whatsapp(payload)


def send_button_message(to: str, body: str, buttons: list[dict]) -> dict | None:
    """
    Send an interactive message with up to 3 reply buttons.

    Args:
        to:      Recipient phone number
        body:    The message text shown above the buttons
        buttons: List of dicts, each with:
                   - "id":    a callback payload string (max 256 chars)
                   - "title": the button label (max 20 chars)

    Example:
        send_button_message("+8801712345678", "Choose an option:", [
            {"id": "my_tasks",     "title": "📋 My Tasks"},
            {"id": "report_issue", "title": "🚨 Report Issue"},
        ])
    """
    # Meta requires exactly this nested structure for interactive buttons
    button_rows = [
        {'type': 'reply', 'reply': {'id': btn['id'], 'title': btn['title']}}
        for btn in buttons[:3]  # Cloud API allows max 3 buttons
    ]

    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body},
            'action': {
                'buttons': button_rows,
            },
        },
    }
    return _post_to_whatsapp(payload)
