from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

import config

logger = logging.getLogger(__name__)

_last_ratelimit_reset: Optional[float] = None

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

_shared_session = create_session()

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
    max_retries: int = 3
) -> Optional[requests.Response]:
    """
    Perform a GET request with intelligent 429 rate limit detection and backoff.
    Inspects Retry-After and X-Ratelimit-Reset headers to automatically sleep
    the required time before retrying.
    """
    global _last_ratelimit_reset

    for attempt in range(max_retries + 1):
        try:
            response = _shared_session.get(url, params=params, timeout=timeout)
            
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

@dataclass
class PriceHistory:
    days_count: int = 0
    avg_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    historical_discount_percent: Optional[float] = None
    has_recent_price_increase: bool = False
    raw_history: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Deal:
    title: str
    store: str
    current_price: float
    previous_price: Optional[float]
    discount_percent: Optional[int]
    product_link: str
    image_url: Optional[str]
    # Validation against other stores
    search_keywords: Optional[str] = None
    competitor_search_url: Optional[str] = None
    similar_found: bool = False
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    min_competitor_price: Optional[float] = None
    min_competitor_link: Optional[str] = None
    market_discount_percent: Optional[float] = None
    is_truly_cheaper: Optional[bool] = None
    # Price history validation (30 days)
    history: Optional[PriceHistory] = None

@dataclass
class RejectedDeal:
    deal: Deal
    reason: str

def parse_price(price_str: Optional[str]) -> Optional[float]:
    """Parse price string like '$257.596' or '139031' into a float."""
    if not price_str:
        return None
    try:
        cleaned = price_str.replace('$', '').replace('.', '').replace(',', '.').strip()
        return float(cleaned)
    except ValueError:
        return None

def parse_discount(discount_str: Optional[str]) -> Optional[int]:
    """Parse discount string like '46% OFF' into an integer percentage."""
    if not discount_str:
        return None
    try:
        cleaned = discount_str.upper().replace('OFF', '').replace('%', '').strip()
        return int(cleaned)
    except ValueError:
        return None

def fetch_deals_page(page: int = 1, limit: int = 54) -> List[Deal]:
    """Fetch and parse deals from a given page number of HardGamers deals."""
    url = "https://www.hardgamers.com.ar/deals"
    params = {"page": page, "limit": limit}

    logger.info(f"Fetching HardGamers deals page {page} with limit {limit}...")
    response = safe_get(url, params=params, timeout=10)
    if not response or response.status_code != 200:
        logger.error(f"Failed to retrieve deals for page {page}.")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    product_articles = soup.find_all("article", class_="One-Bit-Product")
    
    deals: List[Deal] = []
    for article in product_articles:
        try:
            name_el = article.find("p", class_="product-name")
            title = name_el.get_text(strip=True) if name_el else "Unknown Product"

            store_el = article.find("p", class_="store")
            store = store_el.get_text(strip=True) if store_el else "Unknown Store"

            price_span = article.select_one("p.product-price span[itemprop='price']")
            raw_current_price = price_span.get_text(strip=True) if price_span else None
            if not raw_current_price and price_span:
                raw_current_price = price_span.get("content")
            current_price = parse_price(raw_current_price) or 0.0

            prev_price_el = article.find("p", class_="previous-price")
            previous_price = parse_price(prev_price_el.get_text(strip=True)) if prev_price_el else None

            offer_el = article.find("div", class_="offer")
            discount_percent = parse_discount(offer_el.get_text(strip=True)) if offer_el else None

            img_container = article.find("a", class_="img-container")
            href = img_container.get("href") if img_container else ""
            product_link = f"https://www.hardgamers.com.ar{href}" if href.startswith("/") else href

            img_el = img_container.find("img", class_="img") if img_container else None
            image_url = img_el.get("src") if img_el else None

            deal = Deal(
                title=title,
                store=store,
                current_price=current_price,
                previous_price=previous_price,
                discount_percent=discount_percent,
                product_link=product_link,
                image_url=image_url
            )
            deals.append(deal)
        except Exception:
            continue

    return deals

def fetch_all_deals(max_pages: int = 10) -> List[Deal]:
    """Iterate through pagination pages until no more deals are found or max_pages is reached."""
    all_deals: List[Deal] = []
    page = 1

    while page <= max_pages:
        deals = fetch_deals_page(page=page)
        if not deals:
            logger.info(f"No deals found on page {page}. Stopping pagination.")
            break
        all_deals.extend(deals)
        page += 1

    logger.info(f"Successfully scraped a total of {len(all_deals)} deals across {page - 1} pages.")
    return all_deals

def search_competitors(deal: Deal) -> List[Dict[str, Any]]:
    """Search HardGamers for other stores selling the same or similar product model."""
    tokens = [w for w in re.findall(r'[A-Za-z0-9]+', deal.title.upper()) if len(w) > 1 or w.isdigit()]
    if not tokens:
        deal.search_keywords = ""
        deal.competitor_search_url = ""
        return []

    query = ' '.join(tokens[:5])
    deal.search_keywords = query
    url = f"https://www.hardgamers.com.ar/search?text={urllib.parse.quote(query)}"
    deal.competitor_search_url = url

    response = safe_get(url, timeout=8)
    if not response or response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all("article", class_="One-Bit-Product")
    
    deal_tokens_set = set(tokens)
    competitors = []

    for art in articles:
        try:
            name_el = art.find("p", class_="product-name")
            store_el = art.find("p", class_="store")
            price_span = art.select_one("p.product-price span[itemprop='price']")
            if not name_el or not store_el or not price_span:
                continue

            item_title = name_el.get_text(strip=True)
            item_store = store_el.get_text(strip=True)
            
            # Exclude the store of the deal being analyzed
            if item_store.strip().lower() == deal.store.strip().lower():
                continue

            raw_price = price_span.get("content") or price_span.get_text(strip=True)
            price = parse_price(raw_price)
            if price is None or price <= 0:
                continue

            img_container = art.find("a", class_="img-container")
            href = img_container.get("href") if img_container else ""
            comp_link = f"https://www.hardgamers.com.ar{href}" if href.startswith("/") else href

            item_tokens = [w for w in re.findall(r'[A-Za-z0-9]+', item_title.upper()) if len(w) > 1 or w.isdigit()]
            item_tokens_set = set(item_tokens)
            
            intersection = deal_tokens_set.intersection(item_tokens_set)
            token_ratio = len(intersection) / len(deal_tokens_set) if deal_tokens_set else 0.0
            seq_ratio = SequenceMatcher(None, deal.title.upper(), item_title.upper()).ratio()
            
            if token_ratio >= 0.5 or seq_ratio >= 0.6:
                competitors.append({
                    "store": item_store,
                    "title": item_title,
                    "price": price,
                    "link": comp_link,
                    "similarity": round(max(token_ratio, seq_ratio), 2)
                })
        except Exception:
            continue

    return competitors

def fetch_price_history(product_url: str) -> Optional[PriceHistory]:
    """
    Fetch the product detail page and extract the 30-day price history chart data from JS chartConfig.
    """
    response = safe_get(product_url, timeout=8)
    if not response or response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    scripts = soup.find_all("script")

    chart_config = None
    for script in scripts:
        text = script.get_text()
        if "chartConfig" in text and "labels" in text and "datasets" in text:
            match = re.search(r'var\s+chartConfig\s*=\s*({.*?});', text, re.DOTALL)
            if match:
                try:
                    chart_config = json.loads(match.group(1))
                    break
                except Exception as json_err:
                    logger.warning(f"Failed to parse chartConfig JSON: {json_err}")

    if not chart_config or "data" not in chart_config:
        return None

    labels = chart_config["data"].get("labels", [])
    datasets = chart_config["data"].get("datasets", [])
    if not datasets or "data" not in datasets[0]:
        return None

    prices = datasets[0]["data"]
    if not prices or len(prices) == 0:
        return None

    # Consider all prices except the last point (which is the current deal price today)
    pre_deal_prices = prices[:-1] if len(prices) > 1 else prices
    current_price = float(prices[-1])

    avg_prev = sum(pre_deal_prices) / len(pre_deal_prices) if pre_deal_prices else current_price
    min_prev = min(pre_deal_prices) if pre_deal_prices else current_price
    max_prev = max(pre_deal_prices) if pre_deal_prices else current_price

    # Check if there was a price increase in the last 5 days before the deal drop
    recent_pre_prices = pre_deal_prices[-5:] if len(pre_deal_prices) >= 5 else pre_deal_prices
    older_pre_prices = pre_deal_prices[:-5] if len(pre_deal_prices) > 5 else pre_deal_prices
    
    has_recent_increase = False
    if older_pre_prices and recent_pre_prices:
        older_avg = sum(older_pre_prices) / len(older_pre_prices)
        recent_avg = sum(recent_pre_prices) / len(recent_pre_prices)
        if recent_avg > older_avg * 1.05:  # Price increased > 5% recently before discount
            has_recent_increase = True

    hist_discount = ((avg_prev - current_price) / avg_prev * 100.0) if avg_prev > 0 else 0.0

    raw_history = [{"date": labels[i] if i < len(labels) else f"D{i}", "price": prices[i]} for i in range(len(prices))]

    return PriceHistory(
        days_count=len(prices),
        avg_price=round(avg_prev, 2),
        min_price=round(min_prev, 2),
        max_price=round(max_prev, 2),
        historical_discount_percent=round(hist_discount, 1),
        has_recent_price_increase=has_recent_increase,
        raw_history=raw_history
    )
