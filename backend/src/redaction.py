"""Basic privacy defence in depth.

Scope is deliberately narrow: contiguous or lightly separated Chinese mainland mobile
numbers, e-mail addresses and 18-digit ID numbers. It is **not** anonymisation —
`138****5678` can still be reversed by exhaustive search over the hidden digits, and
bank card numbers, names, free-text addresses, faces and on-screen images are not
covered at all. Anything exported to another service must still be reviewed by a
human, and the UI/report say so.
"""
import re

# 13812345678, 138-1234-5678, 138 1234 5678, +86 138 1234 5678
_MOBILE = re.compile(
    r'(?<!\d)(?:\+?86[\s-]?)?(1[3-9]\d)[\s-]?\d{4}[\s-]?(\d{4})(?!\d)')
_EMAIL = re.compile(r'(?i)(?<![\w.+-])[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})(?![\w.-])')
_ID_CARD = re.compile(r'(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)')


def redact(value: str) -> str:
    s = value if isinstance(value, str) else ""
    s = _ID_CARD.sub(lambda m: m.group(1) + "********" + m.group(2), s)
    s = _MOBILE.sub(lambda m: m.group(1) + "****" + m.group(2), s)
    s = _EMAIL.sub(lambda m: "***@" + m.group(1), s)
    return s[:1500]
