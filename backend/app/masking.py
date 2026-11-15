"""Mask sensitive data before anything is stored or shown.

Bug titles in payments teams often contain card numbers, account numbers or
customer emails pasted from logs. They are masked on the way in, so they never
reach the database, the dashboard or an export.
"""
import re

_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_ACCOUNT = re.compile(r"\b\d{8,17}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _mask_digits(digits: str) -> str:
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_text(text: str) -> str:
    if not text:
        return text

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return _mask_digits(digits)
        return m.group(0)

    text = _CARD.sub(card, text)
    text = _IBAN.sub(lambda m: m.group(0)[:4] + "****" + m.group(0)[-4:], text)
    text = _ACCOUNT.sub(lambda m: _mask_digits(m.group(0)), text)
    text = _EMAIL.sub(lambda m: m.group(0)[0] + "***@" + m.group(0).split("@", 1)[1], text)
    return text
