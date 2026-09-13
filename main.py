import argparse
import logging
import sys
import config
from scraper import fetch_all_deals
from analyzer import filter_deals, sort_deals
from notifier import send_email_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="HardGamers Deals Scraper, Market & History Validator Agent")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum number of deal pages to scrape")
    parser.add_argument("--min-discount", type=int, default=30, help="Minimum discount percentage filter")
    parser.add_argument("--min-price-drop", type=float, default=None, help="Minimum absolute price drop in ARS")
    parser.add_argument(
        "--min-competitor-discount",
        type=float,
        default=config.MIN_COMPETITOR_DISCOUNT_PERCENT,
        help=f"Minimum required reduction percentage vs cheapest competitor to accept deal (default: {config.MIN_COMPETITOR_DISCOUNT_PERCENT}%%)"
    )
    parser.add_argument("--include", type=str, help="Comma-separated keywords to include")
    parser.add_argument("--exclude", type=str, help="Comma-separated keywords to exclude")
    parser.add_argument(
        "--max-deals-to-validate", 
        type=int, 
        default=50,
        help="Maximum number of candidate deals to validate deep network requests for"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help=f"Delay in seconds between sequential article validations (default: {config.REQUEST_DELAY_SECONDS}s)"
    )
    parser.add_argument(
        "--sort-by", 
        type=str, 
        default="discount", 
        choices=["discount", "market_discount", "price_drop", "price_asc"], 
        help="Sort criteria for deals"
    )

    parser.add_argument("--no-validate-market", action="store_true", help="Skip searching and validating against other vendors")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email notifications (dry run)")
    parser.add_argument("--limit-output", type=int, default=10, help="Number of top deals to display in console")

    args = parser.parse_args()

    logger.info("Iniciando recolección, validación de mercado e historial de precios de HardGamers...")

    # 1. Scrape deals
    all_deals = fetch_all_deals(max_pages=args.max_pages)
    if not all_deals:
        logger.info("No se pudieron obtener ofertas. Finalizando.")
        return

    # 2. Filter & Validate (Market + 30-Day History sequentially with rate limit protection)
    include_keywords = args.include.split(",") if args.include else None
    exclude_keywords = args.exclude.split(",") if args.exclude else None
    
    filtered_deals, rejected_deals = filter_deals(
        all_deals, 
        min_discount=args.min_discount, 
        min_price_drop=args.min_price_drop,
        min_competitor_discount=args.min_competitor_discount,
        validate_market=not args.no_validate_market,
        max_deals_to_validate=args.max_deals_to_validate,
        delay_between_deals=args.delay,
        include_keywords=include_keywords,
        exclude_keywords=exclude_keywords
    )

    sorted_deals = sort_deals(filtered_deals, by=args.sort_by) if filtered_deals else []

    # 3. Display summary of accepted deals in console
    print("\n" + "=" * 85)
    print(f"RESUMEN DE OFERTAS ACEPTADAS Y VALIDACIÓN (Top {min(args.limit_output, len(sorted_deals))} de {len(sorted_deals)})")
    print("=" * 85)

    if sorted_deals:
        for i, deal in enumerate(sorted_deals[:args.limit_output], 1):
            discount_str = f" ({deal.discount_percent}% OFF tienda)" if deal.discount_percent else ""
            prev_str = f" [antes ${deal.previous_price:,.2f}]" if deal.previous_price else ""
            
            print(f"\n{i}. [{deal.store}] {deal.title}")
            print(f"   Precio oferta: ${deal.current_price:,.2f}{prev_str}{discount_str}")
            print(f"   Link oferta: {deal.product_link}")

            # Competitor validation display
            if deal.competitor_search_url:
                print(f"   🔍 Endpoint búsqueda competencia: {deal.competitor_search_url}")
            elif deal.search_keywords:
                print(f"   🔍 Palabras clave búsqueda: '{deal.search_keywords}'")

            if deal.similar_found and deal.competitors:
                best_comp = deal.competitors[0]
                comp_link_str = f"\n      Link competidor: {best_comp.get('link')}" if best_comp.get("link") else ""
                if deal.is_truly_cheaper and deal.market_discount_percent and deal.market_discount_percent > 0:
                    print(f"   ✅ COMPETENCIA: ¡Es {deal.market_discount_percent}% MÁS BARATO que la competencia!")
                    print(f"      Mejor competidor: [{best_comp['store']}] ${best_comp['price']:,.2f} ({best_comp['title'][:45]}...){comp_link_str}")
                elif deal.market_discount_percent is not None and deal.market_discount_percent <= 0:
                    print(f"   ⚠️ COMPETENCIA: Encontrado en [{best_comp['store']}] a ${best_comp['price']:,.2f}{comp_link_str}")
                else:
                    print(f"   📊 Competidor más cercano: [{best_comp['store']}] ${best_comp['price']:,.2f}{comp_link_str}")
            else:
                print("   ℹ️ COMPETENCIA: Sin productos similares encontrados en otras tiendas.")

            # 30-day Price history display
            if deal.history and deal.history.days_count > 0:
                hist = deal.history
                warn_str = " ⚠️ [ALERTA SUBA PREVIA DETECTADA]" if hist.has_recent_price_increase else ""
                print(f"   📈 HISTORIAL 30 DÍAS: Promedio previo: ${hist.avg_price:,.2f} | Mínimo: ${hist.min_price:,.2f}")
                print(f"      Descuento real vs promedio 30 días: {hist.historical_discount_percent}%{warn_str}")
            else:
                print("   ℹ️ HISTORIAL: No hay datos de gráfico de precios disponibles.")
    else:
        print("\nNinguna oferta cumplió con los criterios de validación (descuento propio y >=10% vs competencia).")

    # 4. Display rejected deals summary in console
    if rejected_deals:
        print("\n" + "=" * 85)
        print(f"LISTADO DE ARTÍCULOS ANALIZADOS Y RECHAZADOS (Total: {len(rejected_deals)})")
        print("=" * 85)
        for i, rej in enumerate(rejected_deals, 1):
            price_str = f"${rej.deal.current_price:,.2f}" if rej.deal.current_price else "N/A"
            disc_str = f" ({rej.deal.discount_percent}% OFF)" if rej.deal.discount_percent else ""
            print(f"{i:3d}. [{rej.deal.store}] {rej.deal.title}")
            print(f"     Precio oferta: {price_str}{disc_str} | Link: {rej.deal.product_link}")
            print(f"     ❌ Causa de rechazo: {rej.reason}")
        print("=" * 85)

    # 5. Send notification email
    if args.no_email:
        logger.info("Modo dry-run activado (--no-email). Envío de email omitido.")
    else:
        logger.info("Enviando reporte por email...")
        success = send_email_alert(sorted_deals, rejected_deals=rejected_deals)
        if success:
            logger.info("Notificación enviada exitosamente.")
        else:
            logger.error("No se pudo enviar la notificación por correo.")

if __name__ == "__main__":
    main()
