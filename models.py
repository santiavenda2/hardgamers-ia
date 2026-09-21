from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


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
class Article:
    title: str
    store: str
    current_price: float
    previous_price: Optional[float]
    discount_percent: Optional[int]
    product_link: str
    image_url: Optional[str]
    source: str


@dataclass
class Deal(Article):
    # Validation against other stores
    search_keywords: Optional[str] = None
    competitor_search_url: Optional[str] = None
    similar_found: bool = False
    competitors: List[Article] = field(default_factory=list)
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


@dataclass
class ProductWithTargetPrice:
    keywords: list[str]
    target_price: float
    exact : Optional[bool] = False