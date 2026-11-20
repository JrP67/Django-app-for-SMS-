from django import forms

from .phone import normalize_phone_number

MAX_MESSAGE_LENGTH = 1600  # generous cap; long texts are split into several SMS segments


class SMSForm(forms.Form):
    recipient = forms.CharField(
        label="Recipient phone number",
        max_length=25,
        error_messages={"required": "Enter the recipient's phone number."},
        widget=forms.TextInput(
            attrs={
                "placeholder": "+639171234567 or 09171234567",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )
    message = forms.CharField(
        label="Message",
        max_length=MAX_MESSAGE_LENGTH,
        error_messages={
            "required": "Write a message before sending.",
            "max_length": f"Message is too long (maximum {MAX_MESSAGE_LENGTH} characters).",
        },
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Type your SMS message here...",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attach aria-invalid and error styling classes when validation fails
        if self.is_bound:
            for name, field in self.fields.items():
                if name in self.errors:
                    existing = field.widget.attrs.get("class", "")
                    field.widget.attrs["class"] = (existing + " is-invalid").strip()
                    field.widget.attrs["aria-invalid"] = "true"
                    field.widget.attrs["aria-describedby"] = f"error_{name}"

    def clean_recipient(self):
        try:
            return normalize_phone_number(self.cleaned_data.get("recipient", ""))
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

    def clean_message(self):
        raw = self.cleaned_data.get("message", "")
        # Normalize Windows CRLF to LF so character & segment counts match SMS encoding
        normalized = raw.replace("\r\n", "\n").strip()
        if not normalized:
            raise forms.ValidationError("Write a message before sending (blank spaces alone aren't valid).")
        if len(normalized) > MAX_MESSAGE_LENGTH:
            raise forms.ValidationError(
                f"Message exceeds {MAX_MESSAGE_LENGTH} characters ({len(normalized)} entered)."
            )
        return normalized
