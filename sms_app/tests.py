from unittest import mock

import requests

from django.utils.html import escape
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import SMSForm
from .models import SMSLog
from .phone import normalize_phone_number
from .services import (
    SendResult,
    SMSConfigurationError,
    SMSConnectionError,
    SMSProviderError,
    fetch_status,
    send_sms,
)


class PhoneNormalizationTests(SimpleTestCase):
    def test_accepts_e164(self):
        self.assertEqual(normalize_phone_number("+639171234567"), "+639171234567")

    def test_strips_formatting(self):
        self.assertEqual(normalize_phone_number("+63 917-123-4567"), "+639171234567")
        self.assertEqual(normalize_phone_number("(0917) 123-4567"), "+639171234567")

    def test_converts_local_ph_number(self):
        self.assertEqual(normalize_phone_number("09171234567"), "+639171234567")
        self.assertEqual(normalize_phone_number("9171234567"), "+639171234567")
        self.assertEqual(normalize_phone_number("639171234567"), "+639171234567")

    def test_rejects_empty_missing_plus_and_garbage(self):
        for bad in ["", "   ", "12345", "+12", "+63abc1234567", "hello"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    normalize_phone_number(bad)


class FormValidationTests(SimpleTestCase):
    def test_invalid_form_adds_aria_attributes(self):
        form = SMSForm(data={"recipient": "12345", "message": "   "})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.fields["recipient"].widget.attrs.get("aria-invalid"), "true")
        self.assertEqual(form.fields["message"].widget.attrs.get("aria-invalid"), "true")
        self.assertIn("is-invalid", form.fields["recipient"].widget.attrs.get("class", ""))

    def test_normalizes_crlf_and_strips_message(self):
        form = SMSForm(data={"recipient": "09171234567", "message": "  Line 1\r\nLine 2  "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["recipient"], "+639171234567")
        self.assertEqual(form.cleaned_data["message"], "Line 1\nLine 2")


class SendViewTests(TestCase):
    url = "/"

    @mock.patch("sms_app.views.send_sms")
    def test_valid_submission_sends_and_logs(self, send):
        send.return_value = SendResult(sid="SM123", status="pending")
        response = self.client.post(self.url, {"recipient": "09171234567", "message": "Hello"})
        self.assertRedirects(response, self.url)
        send.assert_called_once_with("+639171234567", "Hello")
        log = SMSLog.objects.get()
        self.assertEqual((log.status, log.provider_sid), ("pending", "SM123"))

    @mock.patch("sms_app.views.send_sms")
    def test_empty_recipient_is_rejected(self, send):
        response = self.client.post(self.url, {"recipient": "", "message": "Hello"})
        self.assertContains(response, "Enter the recipient")
        send.assert_not_called()
        self.assertEqual(SMSLog.objects.count(), 0)

    @mock.patch("sms_app.views.send_sms")
    def test_empty_message_is_rejected(self, send):
        response = self.client.post(self.url, {"recipient": "+639171234567", "message": "  "})
        self.assertContains(response, "Write a message")
        send.assert_not_called()

    @mock.patch("sms_app.views.send_sms")
    def test_invalid_number_is_rejected(self, send):
        response = self.client.post(self.url, {"recipient": "12345", "message": "Hi"})
        self.assertContains(response, "country code")
        send.assert_not_called()

    @mock.patch("sms_app.views.send_sms")
    def test_provider_errors_are_shown_and_logged(self, send):
        for error in [
            SMSProviderError("The gateway rejected the message."),
            SMSConnectionError("Couldn't reach the SMS gateway."),
            SMSConfigurationError("The gateway rejected the username or password."),
        ]:
            with self.subTest(error=type(error).__name__):
                send.side_effect = error
                response = self.client.post(
                    self.url, {"recipient": "+639171234567", "message": "Hi"}
                )
                self.assertContains(response, escape(error.user_message))
        self.assertEqual(SMSLog.objects.filter(status="failed").count(), 3)


def fake_response(status=200, payload=None):
    response = mock.Mock(status_code=status, text="")
    response.ok = status < 400
    response.json.return_value = payload if payload is not None else {}
    return response


@override_settings(
    SMSGATE_USERNAME="user",
    SMSGATE_PASSWORD="pass",
    SMSGATE_BASE_URL="https://gateway.test/v1",
    SMSGATE_TIMEOUT_SECONDS=5,
)
class ServiceTests(SimpleTestCase):
    @override_settings(SMSGATE_USERNAME="", SMSGATE_PASSWORD="")
    def test_missing_credentials_raise_configuration_error(self):
        with self.assertRaises(SMSConfigurationError) as ctx:
            send_sms("+639171234567", "Hi")
        self.assertIn("SMSGATE_USERNAME", ctx.exception.user_message)

    @mock.patch("sms_app.services.requests.request")
    def test_success_returns_id_and_status(self, request):
        request.return_value = fake_response(202, {"id": "abc123", "state": "Pending"})
        result = send_sms("+639171234567", "Hi")
        self.assertEqual((result.sid, result.status), ("abc123", "pending"))
        _, kwargs = request.call_args
        self.assertEqual(kwargs["json"]["phoneNumbers"], ["+639171234567"])

    @mock.patch("sms_app.services.requests.request")
    def test_wrong_password_is_a_configuration_error(self, request):
        request.return_value = fake_response(401)
        with self.assertRaises(SMSConfigurationError) as ctx:
            send_sms("+639171234567", "Hi")
        self.assertNotIn("pass", ctx.exception.user_message.lower().replace("password", ""))

    @mock.patch("sms_app.services.requests.request")
    def test_bad_request_is_a_provider_error(self, request):
        request.return_value = fake_response(400)
        with self.assertRaises(SMSProviderError):
            send_sms("+639171234567", "Hi")

    @mock.patch("sms_app.services.requests.request")
    def test_network_failure_is_a_connection_error(self, request):
        for exc in [requests.exceptions.ConnectionError(), requests.exceptions.Timeout()]:
            with self.subTest(exc=type(exc).__name__):
                request.side_effect = exc
                with self.assertRaises(SMSConnectionError):
                    send_sms("+639171234567", "Hi")

    @mock.patch("sms_app.services.requests.request")
    def test_fetch_status_lowercases_state(self, request):
        request.return_value = fake_response(200, {"id": "abc123", "state": "Delivered"})
        self.assertEqual(fetch_status("abc123"), "delivered")


class HistoryTests(TestCase):
    def test_empty_history_shows_prompt(self):
        self.assertContains(self.client.get("/history/"), "No messages dispatched yet")

    @mock.patch("sms_app.views.fetch_status", return_value="delivered")
    def test_refresh_updates_status(self, fetch):
        log = SMSLog.objects.create(recipient="+639171234567", body="Hi", status="sent", provider_sid="SM1")
        self.client.post(reverse("refresh_status", args=[log.pk]))
        log.refresh_from_db()
        self.assertEqual(log.status, "delivered")

    def test_refresh_requires_post(self):
        log = SMSLog.objects.create(recipient="+639171234567", body="Hi", status="sent", provider_sid="SM1")
        self.assertEqual(self.client.get(reverse("refresh_status", args=[log.pk])).status_code, 405)
