"""SMS provider abstraction.

Supports: console, file (append JSON lines), and Twilio REST API when credentials
are configured. If SMS_PROVIDER=twilio but credentials are still placeholders,
messages are logged to file (same as local dev) so the app keeps working.
"""


import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .settings import settings


class SMSDeliveryError(RuntimeError):
    """Raised when a configured SMS provider fails to send."""


def twilio_credentials_configured() -> bool:
    """True when Twilio Account SID and auth token look like real values."""
    sid = (settings.twilio_account_sid or '').strip()
    token = (settings.twilio_auth_token or '').strip()
    if not sid or not token:
        return False
    if sid.lower() == 'placeholder' or token.lower() == 'placeholder':
        return False
    # Live Twilio Account SIDs start with AC (34 chars typical)
    return sid.startswith('AC') and len(sid) >= 32


def sms_delivery_mode() -> str:
    """Short label for /health and logs (file, console, twilio, or placeholder)."""
    if settings.sms_provider == 'twilio':
        return 'twilio' if twilio_credentials_configured() else 'placeholder'
    return settings.sms_provider


def _append_sms_log(payload: dict[str, Any]) -> None:
    log_path = Path(settings.sms_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


def _send_twilio_rest(to_phone: str, message: str) -> dict[str, Any]:
    """POST to Twilio Messages API (application/x-www-form-urlencoded)."""
    account_sid = settings.twilio_account_sid.strip()
    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    data: dict[str, str] = {
        'To': to_phone,
        'From': settings.twilio_from_phone.strip(),
        'Body': message,
    }
    cb = (settings.sms_status_callback_url or '').strip()
    if cb and cb.lower() != 'placeholder':
        data['StatusCallback'] = cb

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            data=data,
            auth=(account_sid, settings.twilio_auth_token.strip()),
        )

    if response.status_code >= 400:
        detail = response.text
        try:
            err = response.json()
            detail = err.get('message', detail)
        except Exception:
            pass
        raise SMSDeliveryError(f'Twilio error {response.status_code}: {detail}')

    body = response.json()
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'provider': 'twilio',
        'to': to_phone,
        'message': message,
        'status': body.get('status', 'sent'),
        'twilio_sid': body.get('sid'),
        'placeholder': False,
        'status_callback_url': data.get('StatusCallback'),
    }


class SMSClient:
    def send(self, to_phone: str, message: str) -> dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()

        if settings.sms_provider == 'console':
            payload: dict[str, Any] = {
                'timestamp': timestamp,
                'provider': 'console',
                'to': to_phone,
                'message': message,
                'status': 'printed',
                'placeholder': False,
            }
            print(json.dumps(payload, ensure_ascii=False))
            return payload

        if settings.sms_provider == 'file':
            payload = {
                'timestamp': timestamp,
                'provider': 'file',
                'to': to_phone,
                'message': message,
                'status': 'sent',
                'placeholder': False,
            }
            _append_sms_log(payload)
            return payload

        if settings.sms_provider == 'twilio':
            if twilio_credentials_configured():
                payload = _send_twilio_rest(to_phone, message)
                _append_sms_log(payload)
                return payload

            # Dev / misconfiguration: same as file logging, clearly marked
            payload = {
                'timestamp': timestamp,
                'provider': 'twilio',
                'to': to_phone,
                'message': message,
                'status': 'logged',
                'placeholder': True,
                'note': 'Twilio credentials not configured; message logged only.',
            }
            _append_sms_log(payload)
            return payload

        raise RuntimeError(f'Unsupported SMS provider: {settings.sms_provider}')


sms_client = SMSClient()
