"""Basic privacy defense in depth; MUST still review free-text addresses and images."""
import re
_MOBILE=re.compile(r'(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)')
_EMAIL=re.compile(r'(?i)(?<![\w.+-])[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})(?![\w.-])')
_ID_CARD=re.compile(r'(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)')
def redact(value: str)->str:
    s=value if isinstance(value,str) else ""
    s=_ID_CARD.sub(lambda m:m.group(1)+"********"+m.group(2),s)
    s=_MOBILE.sub(lambda m:m.group(1)+"****"+m.group(2),s)
    s=_EMAIL.sub(lambda m:"***@"+m.group(1),s)
    return s[:1500]
