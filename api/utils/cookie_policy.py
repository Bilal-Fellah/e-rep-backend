"""Single source of truth for auth cookie `Secure` / `SameSite` flags.

`SameSite=None` is only honoured by browsers when the cookie is also `Secure`;
a `None`/insecure pair is rejected outright, which shows up as a silent total
auth failure with no error anywhere. Deriving both flags here keeps that pair
from ever being emitted, whatever `COOKIE_SECURE` is set to.
"""

import logging
import os

logger = logging.getLogger(__name__)

_VALID_SAMESITE = ("Strict", "Lax", "None")


def _resolve():
    secure = os.environ.get("COOKIE_SECURE", "true").lower() == "true"

    raw = os.environ.get("COOKIE_SAMESITE", "None").strip()
    samesite = next((v for v in _VALID_SAMESITE if v.lower() == raw.lower()), None)
    if samesite is None:
        logger.warning(
            "COOKIE_SAMESITE=%r is not one of %s — falling back to 'None'",
            raw,
            _VALID_SAMESITE,
        )
        samesite = "None"

    if samesite == "None" and not secure:
        # Emitting this pair would make every browser drop the cookie.
        logger.warning(
            "COOKIE_SAMESITE='None' requires COOKIE_SECURE=true; browsers reject "
            "the pair. Falling back to SameSite='Lax'. Cross-site cookie delivery "
            "(the brendex.net -> app.brendex.net handoff, Google OAuth) will not "
            "work in this configuration."
        )
        samesite = "Lax"

    return secure, samesite


COOKIE_SECURE, COOKIE_SAMESITE = _resolve()
