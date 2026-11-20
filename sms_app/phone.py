"""Phone number cleaning & validation. Pure Python so it is easy to test and reuse."""
import re

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone_number(raw):
    """Return the number in E.164 format (e.g. +639171234567) or raise ValueError.

    Accepts spaces, dashes, dots, and parentheses.
    Supports:
    - International numbers starting with '+' or '00'
    - Philippine local mobile numbers starting with '09' (11 digits -> +639...)
    - Philippine mobile numbers starting with '9' (10 digits -> +639...)
    - Philippine mobile numbers starting with '639' without '+' (12 digits -> +639...)
    """
    cleaned = re.sub(r"[\s\-().]", "", (raw or "").strip())
    if not cleaned:
        raise ValueError("Enter the recipient's phone number.")

    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif re.fullmatch(r"09\d{9}", cleaned):
        cleaned = "+63" + cleaned[1:]
    elif re.fullmatch(r"9\d{9}", cleaned):
        cleaned = "+63" + cleaned
    elif re.fullmatch(r"639\d{9}", cleaned):
        cleaned = "+" + cleaned

    if not cleaned.startswith("+"):
        raise ValueError(
            "Start the number with a country code (e.g. +639171234567) or use a Philippine 09 number."
        )
    if not E164_RE.match(cleaned):
        raise ValueError(
            "That doesn't look like a valid phone number. "
            "Use international format (+639171234567) or 11-digit local format (09171234567)."
        )
    return cleaned
