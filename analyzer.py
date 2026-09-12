import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from scraper import Deal, search_competitors, fetch_price_history
import config

logger = logging.getLogger(__name__)

def validate_single_deal(deal: Deal) -> Deal:
    """
    Validate a single deal against market competitors and 30-day price history.
    """
    # 1. Market Competitor Search
    try:
        competitors = search_competitors(deal)
        if competitors:
            competitors.sort(key=lambda x: x["price"])
            min_comp_price = competitors[0]["price"]

            deal.similar_found = True
            deal.competitors = competitors
            deal.min_competitor_price = min_comp_price
            
            if min_comp_price > 0:
                market_discount = ((min_comp_price - deal.current_price) / min_comp_price) * 100.0
                deal.market_discount_percent = round(market_discount, 1)
                deal.is_truly_cheaper = deal.current_price < min_comp_price
            else:
                deal.market_discount_percent = 0.0
                deal.is_truly_cheaper = False
        else:
            deal.similar_found = False
            deal.competitors = []
            deal.min_competitor_price = None
            deal.market_discount_percent = None
            deal.is_truly_cheaper = None
    except Exception as e:
        logger.warning(f"Market search failed for '{deal.title}': {e}")

    # 2. Fetch 30-day Price History
    try:
        time.sleep(0.1)
        history = fetch_price_history(deal.product_link)
        deal.history = history
    except Exception as e:
        logger.warning(f"History fetch failed for '{deal.title}': {e}")

    return deal

def filter_deals(
    deals: List[Deal], 
    min_discount: Optional[int] = None, 
    min_price_drop: Optional[float] = None,
    validate_market: bool = True,
    max_deals_to_validate: int = 15,
    max_workers: int = 3,
    include_keywords: Optional[List[str]] = None,
    exclude_keywords: Optional[List[str]] = None
) -> List[Deal]:
    """
    Filter deals based on minimum discount, price drop, and keywords.
    """
    if min_discount is None:
        min_discount = config.MIN_DISCOUNT_PERCENT
    if min_price_drop is None:
        min_price_drop = config.MIN_PRICE_DROP_ARS
    if include_keywords is None:
        include_keywords = [k.strip() for k in config.INCLUDE_KEYWORDS.split(",")] if config.INCLUDE_KEYWORDS else []
    if exclude_keywords is None:
        exclude_keywords = [k.strip() for k in config.EXCLUDE_KEYWORDS.split(",")] if config.EXCLUDE_KEYWORDS else []

    # First pass: Filter
    candidates = []
    for deal in deals:
        # Basic filters
        matched_basic = False
        if deal.discount_percent is not None and deal.discount_percent >= min_discount:
            matched_basic = True
        elif deal.previous_price is not None and deal.current_price is not None:
            drop = deal.previous_price - deal.current_price
            if drop >= min_price_drop:
                matched_basic = True
        
        if not matched_basic:
            continue
            
        # Keyword filter
        title = deal.title.lower()
        if exclude_keywords and any(ex.lower() in title for ex in exclude_keywords):
            continue
        if include_keywords and not any(inc.lower() in title for inc in include_keywords):
            continue
            
        candidates.append(deal)

    logger.info(f"Initial filter: {len(deals)} deals -> {len(candidates)} candidates matching threshold and keywords.")

    # Validation
    if validate_market and candidates:
        candidates.sort(key=lambda d: d.discount_percent or 0, reverse=True)
        deals_to_validate = candidates[:max_deals_to_validate]
        
        logger.info(f"Validating {len(deals_to_validate)} candidates against competitors...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_deal = {executor.submit(validate_single_deal, d): d for d in deals_to_validate}
            for future in as_completed(future_to_deal):
                pass # Already updated in place

        return deals_to_validate

    return candidates

def sort_deals(deals: List[Deal], by: str = "discount") -> List[Deal]:
    if by == "market_discount":
        return sorted(deals, key=lambda d: (d.similar_found, d.market_discount_percent or -999), reverse=True)
    elif by == "discount":
        return sorted(deals, key=lambda d: d.discount_percent if d.discount_percent is not None else 0, reverse=True)
    elif by == "price_drop":
        return sorted(deals, key=lambda d: (d.previous_price - d.current_price) if (d.previous_price and d.current_price) else 0, reverse=True)
    elif by == "price_asc":
        return sorted(deals, key=lambda d: d.current_price)
    else:
        return deals
