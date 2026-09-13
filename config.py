import os

def _get_env_str(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    return val.strip() if val is not None and val.strip() else default

def _get_env_int(key: str, default: int) -> int:
    val = os.environ.get(key, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def _get_env_float(key: str, default: float) -> float:
    val = os.environ.get(key, "").strip()
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default

# HardGamers URLs & Scraping settings
HARDGAMERS_BASE_URL = "https://www.hardgamers.com.ar"
HARDGAMERS_DEALS_URL = f"{HARDGAMERS_BASE_URL}/deals"
LIMIT_PER_PAGE = 54

# Standard request headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Scraping rate limit / pacing settings
REQUEST_DELAY_SECONDS = _get_env_float("REQUEST_DELAY_SECONDS", 1.5)

# SMTP Configuration
SMTP_SERVER = _get_env_str("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = _get_env_int("SMTP_PORT", 587)
SMTP_USER = _get_env_str("SMTP_USER", "")
SMTP_PASSWORD = _get_env_str("SMTP_PASSWORD", "")

# Email settings
EMAIL_FROM = _get_env_str("EMAIL_FROM", "")
EMAIL_TO = _get_env_str("EMAIL_TO", "")  # Can be comma-separated list

def is_email_configured() -> bool:
    """Check if all required SMTP settings are present."""
    return bool(SMTP_USER and SMTP_PASSWORD and EMAIL_TO)

# Deal Analyzer Configuration
MIN_DISCOUNT_PERCENT = _get_env_int("MIN_DISCOUNT_PERCENT", 20)
MIN_PRICE_DROP_ARS = _get_env_float("MIN_PRICE_DROP_ARS", 500.0)
MIN_COMPETITOR_DISCOUNT_PERCENT = _get_env_float("MIN_COMPETITOR_DISCOUNT_PERCENT", 10.0)

# Filtering configuration (comma-separated strings)
# Ejemplo: INCLUDE_KEYWORDS = "monitor,lg" (solo incluirá productos que contengan monitor O lg)
INCLUDE_KEYWORDS = _get_env_str("INCLUDE_KEYWORDS", "")
EXCLUDE_KEYWORDS = _get_env_str("EXCLUDE_KEYWORDS", "switch")
