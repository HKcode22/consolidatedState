from __future__ import annotations

import hmac


def passcode_matches(
    supplied: str,
    configured: str,
) -> bool:
    """Constant-time passcode comparison for the optional family-use gate."""
    if not configured:
        return True

    return hmac.compare_digest(
        supplied.encode("utf-8"),
        configured.encode("utf-8"),
    )
