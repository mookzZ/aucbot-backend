import hashlib
import hmac
from urllib.parse import unquote
from app.config import settings


def validate_init_data(init_data: str) -> dict | None:
    """
    Validates Telegram WebApp initData signature.
    Returns parsed data dict if valid, None if invalid.
    """
    parsed = {}
    pairs = []

    for part in unquote(init_data).split("&"):
        if "=" in part:
            key, _, value = part.partition("=")
            if key == "hash":
                received_hash = value
            else:
                pairs.append(f"{key}={value}")
                parsed[key] = value

    pairs.sort()
    data_check_string = "\n".join(pairs)

    secret_key = hmac.new(
        b"WebAppData", settings.bot_token.encode(), hashlib.sha256
    ).digest()

    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    # parse user JSON if present
    import json
    if "user" in parsed:
        try:
            parsed["user"] = json.loads(parsed["user"])
        except Exception:
            pass

    return parsed
