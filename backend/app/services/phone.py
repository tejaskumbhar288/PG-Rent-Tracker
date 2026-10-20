"""Phone-number normalisation.

Indian mobile numbers only — the MVP serves one PG owner in India (CLAUDE.md §2).
This lives in a service rather than inside a schema so the same rule serves both
signup validation and the login lookup.
"""

import re

# Everything an owner might type as separators, including a non-breaking space.
_SEPARATORS = re.compile(r"[\s \-().]")
_TEN_DIGITS = re.compile(r"^[6-9]\d{9}$")

COUNTRY_CODE = "+91"


def normalize_phone(raw: str) -> str:
    """Return ``raw`` as an E.164 Indian mobile number (``+91XXXXXXXXXX``).

    Accepts the forms an owner actually writes: ``98765 43210``, ``09876543210``,
    ``919876543210``, ``+91-98765-43210``.

    Raises:
        ValueError: if the input is not a recognisable Indian mobile number.
    """
    cleaned = _SEPARATORS.sub("", raw or "")

    if cleaned.startswith(COUNTRY_CODE):
        digits = cleaned.removeprefix(COUNTRY_CODE)
    elif len(cleaned) == 12 and cleaned.startswith("91"):
        digits = cleaned[2:]
    elif len(cleaned) == 11 and cleaned.startswith("0"):
        digits = cleaned[1:]
    else:
        digits = cleaned

    if not _TEN_DIGITS.match(digits):
        raise ValueError("invalid indian phone number")
    return COUNTRY_CODE + digits
