import os

# HardGamers URLs & Scraping settings
HARDGAMERS_BASE_URL = "https://www.hardgamers.com.ar"
HARDGAMERS_DEALS_URL = f"{HARDGAMERS_BASE_URL}/deals"
LIMIT_PER_PAGE = 54

# Standard request headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# SMTP Configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# Email settings
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")  # Can be comma-separated list

# Deal Analyzer Configuration
MIN_DISCOUNT_PERCENT = int(os.environ.get("MIN_DISCOUNT_PERCENT", "20"))
MIN_PRICE_DROP_ARS = float(os.environ.get("MIN_PRICE_DROP_ARS", "500"))

# Filtering configuration (comma-separated strings)
# Ejemplo: INCLUDE_KEYWORDS = "monitor,lg" (solo incluirá productos que contengan monitor O lg)
INCLUDE_KEYWORDS = os.environ.get("INCLUDE_KEYWORDS", "")
EXCLUDE_KEYWORDS = os.environ.get("EXCLUDE_KEYWORDS", "switch")

