import logging
import sys

from models import Article
from scraper import HardgamersParser, parse_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def find_discount_for_multiple_products(product_identifiers_and_target_price: list[tuple[str, float]]) -> dict[str, list[Article]]:
    hardgamers_parser = HardgamersParser()
    products_with_target_price_by_product_identifier = {}
    for search_terms, target_price in product_identifiers_and_target_price:
        articles_with_target_price, query = find_discount_for_product(search_terms, target_price, hardgamers_parser)
        if articles_with_target_price:
            products_with_target_price_by_product_identifier[query] = articles_with_target_price

    return products_with_target_price_by_product_identifier


def find_discount_for_product(search_terms: list[str], target_price: int, hardgamers_parser: HardgamersParser) -> tuple[
    list[Article], str]:
    logger.info(f"Searching discount for {search_terms} (target price: {target_price})")
    articles, url, query = hardgamers_parser.search(search_terms, max_price=target_price)

    articles_with_target_price = []

    for article_html in articles:
        article = parse_article(article_html)
        # Esto no es necesario porque ya estoy filtrando por precio, pero lo dejo por si se cuela algun articulo extra
        if article.current_price <= target_price:
            articles_with_target_price.append(article)
        else:
            # Dado que los productos estan ordenados en orden creciente de precios, puedo cortar al primero
            # que supera el precio objetivo
            break
    return articles_with_target_price, query


if __name__ == "__main__":
    product_identifiers_and_target_price = [
        (["274QPF"], 520_000),
        (["32GS85Q"], 730_000),
        (["LOGITECH", "MX KEYS S"], 170_000),
    ]
    products_with_target_price_by_product_identifier = find_discount_for_multiple_products(
        product_identifiers_and_target_price=product_identifiers_and_target_price)
    for product_keyword, article_list in products_with_target_price_by_product_identifier.items():
        print(f"\nProducts with target price for {product_keyword}")
        for article in article_list:
            print(article)
