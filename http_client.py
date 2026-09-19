import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

import config


logger = logging.getLogger(__name__)


def create_session() -> requests.Session:
    """Creates a requests session with automatic retry on transient server errors."""
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(config.HEADERS)
    return session


def extract_wait_time_from_response(response: requests.Response, default_wait: float = 60.0) -> float:
    """
    Extract the rate limit wait time in seconds from a 429 response.
    Checks 'Retry-After' header, 'X-Ratelimit-Reset' header, and recent session reset info.
    """
    global _last_ratelimit_reset

    # 1. Check 'Retry-After' header (standard RFC header, e.g. '60' or HTTP Date)
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            try:
                dt = parsedate_to_datetime(retry_after)
                now = datetime.now(timezone.utc)
                diff = (dt - now).total_seconds()
                if diff > 0:
                    return max(1.0, diff)
            except Exception:
                pass

    # 2. Check 'X-Ratelimit-Reset' header (epoch timestamp)
    reset_header = response.headers.get("X-Ratelimit-Reset")
    if reset_header:
        try:
            reset_ts = float(reset_header)
            now_ts = time.time()
            if reset_ts > now_ts:
                return max(1.0, (reset_ts - now_ts) + 1.0)
        except ValueError:
            pass

    # 3. Check previously cached reset timestamp from earlier 200 responses
    if _last_ratelimit_reset is not None:
        now_ts = time.time()
        if _last_ratelimit_reset > now_ts:
            return max(1.0, (_last_ratelimit_reset - now_ts) + 1.0)

    # 4. Fallback default
    return default_wait


def safe_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    max_retries: int = 3,
    shared_session: Optional[requests.Session] = None,
) -> Optional[requests.Response]:
    """
    Perform a GET request with intelligent 429 rate limit detection and backoff.
    Inspects Retry-After and X-Ratelimit-Reset headers to automatically sleep
    the required time before retrying.
    """
    global _last_ratelimit_reset
    if shared_session is None:
        shared_session = create_session()

    for attempt in range(max_retries + 1):
        try:
            response = shared_session.get(url, params=params, timeout=timeout)

            # Save rate limit reset if provided in headers
            reset_header = response.headers.get("X-Ratelimit-Reset")
            if reset_header:
                try:
                    _last_ratelimit_reset = float(reset_header)
                except ValueError:
                    pass

            if response.status_code == 429:
                if attempt < max_retries:
                    wait_time = extract_wait_time_from_response(response, default_wait=60.0)
                    logger.warning(
                        f"HTTP 429 (Rate Limit) al solicitar {url}. "
                        f"Tiempo de espera indicado por HardGamers: {wait_time:.1f}s. "
                        f"Pausando antes de reintentar (intento {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"HTTP 429 persistente tras {max_retries} reintentos para {url}.")
                    return response

            return response
        except requests.RequestException as e:
            if attempt < max_retries:
                backoff = 2.0 * (attempt + 1)
                logger.warning(f"Error de red ({e}) en {url}. Reintentando en {backoff:.1f}s...")
                time.sleep(backoff)
            else:
                logger.error(f"Error de red definitivo para {url}: {e}")
                return None

    return None
