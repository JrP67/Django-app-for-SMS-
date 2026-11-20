"""Everything that talks to the SMS provider lives here, so views stay simple.

Provider: SMSGate (https://sms-gate.app), an Android app that turns your own
phone into an SMS gateway with a REST API. The app's "Cloud Server" mode gives
you a username and password; this module sends them with HTTP Basic auth.

Every failure becomes an SMSError with a message that is safe to show to the
user. Credentials and raw provider responses are never shown; details go to
the server log only.
"""
import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSError(Exception):
    """Base class. `user_message` is safe to display."""

    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


class SMSConfigurationError(SMSError):
    """Missing or rejected credentials."""


class SMSProviderError(SMSError):
    """The gateway refused the request or answered unexpectedly."""


class SMSConnectionError(SMSError):
    """Couldn't reach the gateway (network down, timeout)."""


@dataclass
class SendResult:
    sid: str     # the gateway's message id
    status: str  # e.g. "pending", "sent", "delivered", "failed"


def _credentials():
    missing = []
    if not settings.SMSGATE_USERNAME:
        missing.append("SMSGATE_USERNAME")
    if not settings.SMSGATE_PASSWORD:
        missing.append("SMSGATE_PASSWORD")
    if missing:
        logger.error("SMS gateway settings missing: %s", ", ".join(missing))
        raise SMSConfigurationError(
            "SMS sending isn't set up yet. Missing settings: " + ", ".join(missing) + "."
        )
    return settings.SMSGATE_USERNAME, settings.SMSGATE_PASSWORD


def _request(method, path, **kwargs):
    """Call the gateway and return its parsed JSON, or raise an SMSError."""
    auth = _credentials()
    url = settings.SMSGATE_BASE_URL.rstrip("/") + path
    try:
        response = requests.request(
            method, url, auth=auth, timeout=settings.SMSGATE_TIMEOUT_SECONDS, **kwargs
        )
    except requests.exceptions.Timeout as exc:
        logger.warning("Gateway timeout: %s", exc)
        raise SMSConnectionError(
            "The SMS gateway took too long to respond. Try again in a moment."
        ) from exc
    except requests.exceptions.RequestException as exc:
        logger.warning("Gateway connection error: %s", exc)
        raise SMSConnectionError(
            "Couldn't reach the SMS gateway. Check your internet connection and SMSGATE_BASE_URL."
        ) from exc

    if response.status_code in (401, 403):
        raise SMSConfigurationError(
            "The SMS gateway rejected the username or password. "
            "Copy them again from the SMSGate app's Cloud Server section."
        )
    if response.status_code == 404:
        raise SMSProviderError("The gateway couldn't find that message.")
    if response.status_code >= 500:
        logger.warning("Gateway server error %s: %s", response.status_code, response.text[:200])
        raise SMSProviderError("The SMS gateway is having problems. Try again later.")
    if not response.ok:
        logger.warning("Gateway rejected request %s: %s", response.status_code, response.text[:200])
        raise SMSProviderError(
            f"The gateway rejected the message (HTTP {response.status_code}). "
            "Check the phone number and message, then try again."
        )
    try:
        return response.json()
    except ValueError as exc:
        raise SMSProviderError("The SMS gateway sent back an unexpected response.") from exc


def send_sms(to, body):
    """Submit one message to the gateway. `to` must already be in E.164 format."""
    data = _request(
        "POST",
        "/messages",
        json={"textMessage": {"text": body}, "phoneNumbers": [to]},
    )
    message_id = data.get("id")
    if not message_id:
        logger.warning("Gateway response had no message id: %s", data)
        raise SMSProviderError("The SMS gateway didn't confirm the message. Please try again.")
    return SendResult(sid=str(message_id), status=str(data.get("state") or "pending").lower())


def fetch_status(sid):
    """Ask the gateway for the latest status of a message we submitted earlier."""
    data = _request("GET", f"/messages/{sid}")
    state = data.get("state")
    if not state:
        raise SMSProviderError("The gateway didn't report a status for that message.")
    return str(state).lower()
