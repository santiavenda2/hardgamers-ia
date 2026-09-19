import logging
import time
from typing import List, Optional, Tuple
from scraper import HardgamersParser
from models import Deal, RejectedDeal
import config

logger = logging.getLogger(__name__)

def validate_single_deal(deal: Deal) -> Deal:
    """
    Validate a single deal against market competitors and 30-day price history.
    """
    logger.info(f"Validating deal: {deal.title}")
    hardgamers_parser = HardgamersParser()
    # 1. Market Competitor Search
    try:
        competitors = hardgamers_parser.search_competitors(deal)
        if competitors:
            competitors.sort(key=lambda x: x["price"])
            min_comp_price = competitors[0]["price"]
            min_comp_link = competitors[0].get("link")

            deal.similar_found = True
            deal.competitors = competitors
            deal.min_competitor_price = min_comp_price
            deal.min_competitor_link = min_comp_link
            
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
            deal.min_competitor_link = None
            deal.market_discount_percent = None
            deal.is_truly_cheaper = None
    except Exception as e:
        logger.warning(f"Market search failed for '{deal.title}': {e}")

    # 2. Fetch 30-day Price History
    try:
        time.sleep(0.2)
        history = hardgamers_parser.fetch_price_history(deal.product_link)
        deal.history = history
    except Exception as e:
        logger.warning(f"History fetch failed for '{deal.title}': {e}")

    return deal

def filter_deals(
    deals: List[Deal], 
    min_discount: Optional[int] = None, 
    min_price_drop: Optional[float] = None,
    min_competitor_discount: Optional[float] = None,
    validate_market: bool = True,
    max_deals_to_validate: int = 50,
    delay_between_deals: Optional[float] = None,
    include_keywords: Optional[List[str]] = None,
    exclude_keywords: Optional[List[str]] = None
) -> Tuple[List[Deal], List[RejectedDeal]]:
    """
    Filter deals based on minimum discount, price drop, and keywords.
    Validates candidates sequentially with a delay between each article to prevent HTTP 429.
    Rejects deals if the cheapest competitor reduction is below min_competitor_discount (default: 10%).
    Returns a tuple containing:
    - List of accepted/validated deals
    - List of rejected deals with their respective rejection reasons
    """
    if min_discount is None:
        min_discount = config.MIN_DISCOUNT_PERCENT
    if min_price_drop is None:
        min_price_drop = config.MIN_PRICE_DROP_ARS
    if min_competitor_discount is None:
        min_competitor_discount = config.MIN_COMPETITOR_DISCOUNT_PERCENT
    if delay_between_deals is None:
        delay_between_deals = config.REQUEST_DELAY_SECONDS
    if include_keywords is None:
        include_keywords = [k.strip() for k in config.INCLUDE_KEYWORDS.split(",") if k.strip()] if config.INCLUDE_KEYWORDS else []
    else:
        include_keywords = [k.strip() for k in include_keywords if k.strip()]
        
    if exclude_keywords is None:
        exclude_keywords = [k.strip() for k in config.EXCLUDE_KEYWORDS.split(",") if k.strip()] if config.EXCLUDE_KEYWORDS else []
    else:
        exclude_keywords = [k.strip() for k in exclude_keywords if k.strip()]

    candidates: List[Deal] = []
    rejected: List[RejectedDeal] = []

    for deal in deals:
        title_lower = deal.title.lower()

        # 1. Keyword exclusion filter
        if exclude_keywords:
            matched_exclude = [ex for ex in exclude_keywords if ex.lower() in title_lower]
            if matched_exclude:
                rejected.append(RejectedDeal(
                    deal=deal,
                    reason=f"Palabra clave excluida: '{', '.join(matched_exclude)}'"
                ))
                continue

        # 2. Keyword inclusion filter
        if include_keywords:
            matched_include = [inc for inc in include_keywords if inc.lower() in title_lower]
            if not matched_include:
                rejected.append(RejectedDeal(
                    deal=deal,
                    reason=f"No contiene palabras clave requeridas ({', '.join(include_keywords)})"
                ))
                continue

        # 3. Discount / Price drop filter
        drop = (deal.previous_price - deal.current_price) if (deal.previous_price is not None and deal.current_price is not None) else None

        if deal.discount_percent is not None:
            if deal.discount_percent >= min_discount:
                candidates.append(deal)
            else:
                rejected.append(RejectedDeal(
                    deal=deal,
                    reason=f"Descuento insuficiente ({deal.discount_percent}% < {min_discount}%)"
                ))
        elif drop is not None:
            if drop >= min_price_drop:
                candidates.append(deal)
            else:
                rejected.append(RejectedDeal(
                    deal=deal,
                    reason=f"Rebaja insuficiente (${drop:,.2f} < ${min_price_drop:,.2f} y sin % de oferta)"
                ))
        else:
            rejected.append(RejectedDeal(
                deal=deal,
                reason="Sin porcentaje de descuento ni precio anterior disponible"
            ))

    logger.info(f"Initial filter: {len(deals)} deals -> {len(candidates)} candidates, {len(rejected)} rejected.")

    # 4. Sequential Market & History Validation
    if validate_market and candidates:
        candidates.sort(key=lambda d: d.discount_percent or 0, reverse=True)
        deals_to_validate = candidates[:max_deals_to_validate]
        unvalidated_candidates = candidates[max_deals_to_validate:]
        
        for d in unvalidated_candidates:
            disc_text = f" ({d.discount_percent}% OFF)" if d.discount_percent else ""
            rejected.append(RejectedDeal(
                deal=d,
                reason=f"Supera el cupo de validación profunda (Top {max_deals_to_validate} por descuento){disc_text}"
            ))

        total_to_validate = len(deals_to_validate)
        logger.info(
            f"Validando secuencialmente {total_to_validate} candidatos con intervalo de {delay_between_deals:.1f}s entre artículos..."
        )

        accepted_deals: List[Deal] = []

        for i, deal in enumerate(deals_to_validate, 1):
            validate_single_deal(deal)
            query_str = f" [Búsqueda: '{deal.search_keywords}']" if deal.search_keywords else ""
            logger.info(f"[{i}/{total_to_validate}] Analizado '{deal.title[:40]}' ({deal.store}){query_str}...")

            # Reject if competitor exists and deal reduction vs cheapest competitor is under min_competitor_discount (10%)
            if deal.similar_found and deal.competitors:
                best_comp = deal.competitors[0]
                market_disc = deal.market_discount_percent if deal.market_discount_percent is not None else 0.0
                comp_link_info = f" | Link competidor: {best_comp.get('link')}" if best_comp.get("link") else ""
                search_url_info = f" | Endpoint búsqueda: {deal.competitor_search_url}" if deal.competitor_search_url else ""
                
                if market_disc < min_competitor_discount:
                    if market_disc <= 0:
                        reason = (
                            f"Competencia más barata o igual en [{best_comp['store']}] a ${best_comp['price']:,.2f}"
                            f"{comp_link_info}{search_url_info}"
                        )
                    else:
                        reason = (
                            f"Reducción insuficiente frente a competencia ({market_disc:.1f}% < {min_competitor_discount:.1f}%). "
                            f"Mejor competidor [{best_comp['store']}] a ${best_comp['price']:,.2f}"
                            f"{comp_link_info}{search_url_info}"
                        )
                    rejected.append(RejectedDeal(deal=deal, reason=reason))
                else:
                    accepted_deals.append(deal)
            else:
                accepted_deals.append(deal)

            if i < total_to_validate and delay_between_deals > 0:
                time.sleep(delay_between_deals)

        return accepted_deals, rejected

    return candidates, rejected

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
