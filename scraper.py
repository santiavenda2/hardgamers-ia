import json
import logging
import re
import urllib.parse
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup, ResultSet, Tag

from http_client import create_session, safe_get
from models import PriceHistory, Deal

SOURCE_HARDGAMERS = "hardgamers"

logger = logging.getLogger(__name__)


class HardgamersParser:

    def __init__(self):
        self._shared_session = create_session()
        _last_ratelimit_reset: Optional[float] = None

    def fetch_deals_page(self, page: int = 1, limit: int = 54) -> List[Deal]:
        """Fetch and parse deals from a given page number of HardGamers deals."""
        url = "https://www.hardgamers.com.ar/deals"
        params = {"page": page, "limit": limit}

        logger.info(f"Fetching HardGamers deals page {page} with limit {limit}...")
        response = safe_get(url, params=params, timeout=10, shared_session=self._shared_session)
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
                    image_url=image_url,
                    source=SOURCE_HARDGAMERS,
                )
                deals.append(deal)
            except Exception:
                continue

        return deals

    def search_competitors(self, deal: Deal) -> List[Dict[str, Any]]:
        """
        Search HardGamers for other stores selling the same or similar product model.
        Since search results are sorted by price ascending (cheapest first),
        the first valid competitor matching similarity criteria is the cheapest competitor.
        """
        product_type, product_model_tokens = extract_product_type_and_model(deal.title.upper())
        if not product_model_tokens:
            deal.search_keywords = ""
            deal.competitor_search_url = ""
            return []

        competitors = []

        while len(product_model_tokens) > 2 and len(competitors) == 0:
            # Busco productos similares usando el modelo, Si no encuentro voy quitando tokens del final del modelo
            query = ' '.join(product_model_tokens)
            deal.search_keywords = query
            url = f"https://www.hardgamers.com.ar/search?text={urllib.parse.quote(query)}"
            deal.competitor_search_url = url

            response = safe_get(url, timeout=8, shared_session=self._shared_session)
            if not response or response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all("article", class_="One-Bit-Product")

            deal_tokens_set = set(product_model_tokens)

            current_competitors = find_competitors_on_similar_articles(articles, deal, deal_tokens_set)
            if current_competitors:
                logger.debug("Competitors found")
                competitors.extend(current_competitors)
            else:
                product_model_tokens = product_model_tokens[:-1]

        return competitors

    def fetch_price_history(self, product_url: str) -> Optional[PriceHistory]:
        """
        Fetch the product detail page and extract the 30-day price history chart data from JS chartConfig.
        """
        response = safe_get(product_url, timeout=8, shared_session=self._shared_session)
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

        raw_history = [{"date": labels[i] if i < len(labels) else f"D{i}", "price": prices[i]} for i in
                       range(len(prices))]

        return PriceHistory(
            days_count=len(prices),
            avg_price=round(avg_prev, 2),
            min_price=round(min_prev, 2),
            max_price=round(max_prev, 2),
            historical_discount_percent=round(hist_discount, 1),
            has_recent_price_increase=has_recent_increase,
            raw_history=raw_history
        )

    def fetch_all_deals(self, max_pages: int = 10, min_discount: Optional[int] = None) -> List[Deal]:
        """
        Iterate through pagination pages. Since HardGamers deals are sorted by discount descending,
        scrapes deals page by page until no more deals are found, max_pages is reached,
        or deals fall below min_discount (early stopping optimization).
        """
        all_deals: List[Deal] = []
        page = 1
        stop_early = False

        while page <= max_pages and not stop_early:
            deals = self.fetch_deals_page(page=page)
            if not deals:
                logger.info(f"No deals found on page {page}. Stopping pagination.")
                break

            for deal in deals:
                if min_discount is not None and deal.discount_percent is not None and deal.discount_percent < min_discount:
                    logger.info(
                        f"Alcanzado producto '{deal.title[:35]}' con descuento ({deal.discount_percent}% OFF) "
                        f"inferior al mínimo buscado ({min_discount}% OFF). "
                        f"Deteniendo paginación de forma anticipada en página {page}."
                    )
                    stop_early = True
                    break
                all_deals.append(deal)

            page += 1

        logger.info(f"Successfully scraped a total of {len(all_deals)} deals across {page - 1} pages.")
        return all_deals

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


def find_competitors_on_similar_articles(articles: ResultSet[Tag], deal: Deal, deal_tokens_set: set[str]) -> list[dict]:
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

            item_type, item_model = extract_product_type_and_model(item_title.upper())
            item_tokens_set = set(item_model)

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
                # Optimization: HardGamers search results are sorted ascending by price.
                # The first matching item is guaranteed to be the cheapest competitor.
                break
        except Exception:
            continue

    return competitors


def extract_product_type_and_model(deal_title: str) -> tuple[str, list[str]]:
    """
    Extract product type and model from the deal title.
    En general en los productos de hardgamers la primera palabra del titulo es el tipo de producto (mouse, teclado, etc)
    TODO: agregar un listado de tipos conocidos (incluyendo tipos de mas de una palabra, ejemplo, silla ergonomica) y
    extraer estos tipos del titulo
    :param deal_title: titulo del deal
    :return: tipo de producto, listado de strings del modelo
    """
    deal_title = deal_title.upper()
    tokens = [w for w in deal_title.split(" ") if len(w) > 1 and re.match(r"^[A-Za-z0-9.\-]+$", w)]
    # tokens = [w for w in re.findall(r'[A-Za-z0-9]+', deal_title) if len(w) > 1 or w.isdigit()]
    product_type = tokens[0]
    product_model = tokens[1:]
    return product_type, product_model


if __name__ == "__main__":
    product_type, product_model = extract_product_type_and_model("ADAPTADOR TIPO C A PLUG 3.5 (H) OFF-ADA002 OFFICE")
    print(product_type, product_model)