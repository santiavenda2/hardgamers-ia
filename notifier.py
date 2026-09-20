import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import List, Optional
from models import Deal, RejectedDeal
import config

logger = logging.getLogger(__name__)

def generate_html_email(deals: List[Deal], rejected_deals: Optional[List[RejectedDeal]] = None) -> str:
    """Generate a clean, responsive HTML email body with the list of deals, market comparison, 30-day history & rejected items."""
    deals_html = ""
    for deal in deals:
        prev_price_html = f"<span class='old-price'>${deal.previous_price:,.2f}</span>" if deal.previous_price else ""
        discount_badge = f"<span class='badge'>{deal.discount_percent}% OFF</span>" if deal.discount_percent else ""
        image_html = f"<img src='{deal.image_url}' alt='{deal.title}' class='deal-img'>" if deal.image_url else ""
        
        search_link_html = ""
        if deal.competitor_search_url:
            search_link_html = f"<div style='font-size: 11px; color: #6c757d; margin-bottom: 4px;'>🔍 <a href='{deal.competitor_search_url}' target='_blank' style='color: #0366d6; text-decoration: underline;'>Endpoint Búsqueda HardGamers</a> (<em>'{deal.search_keywords}'</em>)</div>"

        # Competitor validation block
        if deal.similar_found and deal.competitors:
            best_competitor = deal.competitors[0]
            comp_link_tag = f"<a href='{best_competitor.product_link}' target='_blank' style='color: inherit; text-decoration: underline; font-weight: bold;'>{best_competitor.store}</a>" if best_competitor.product_link else f"<strong>{best_competitor.store}</strong>"

            if deal.is_truly_cheaper and deal.market_discount_percent and deal.market_discount_percent > 0:
                market_html = f"""
                <div class='market-comparison market-cheaper'>
                    {search_link_html}
                    ✅ <strong>¡Más barato que la competencia!</strong> {deal.market_discount_percent}% menos que {comp_link_tag} (${best_competitor.current_price:,.2f})
                </div>
                """
            elif deal.market_discount_percent is not None and deal.market_discount_percent <= 0:
                market_html = f"""
                <div class='market-comparison market-warning'>
                    {search_link_html}
                    ⚠️ Encontrado más barato o igual en {comp_link_tag} (${best_competitor.current_price:,.2f})
                </div>
                """
            else:
                market_html = f"""
                <div class='market-comparison'>
                    {search_link_html}
                    📊 Competidor más cercano: {comp_link_tag} (${best_competitor.current_price:,.2f})
                </div>
                """
        else:
            market_html = f"""
            <div class='market-comparison market-neutral'>
                {search_link_html}
                ℹ️ <em>Sin productos similares encontrados en otras tiendas</em>
            </div>
            """

        # 30-day Price History Block
        history_html = ""
        if deal.history and deal.history.days_count > 0:
            hist = deal.history
            warning_tag = "<span style='color: #d9534f; font-weight: bold;'> ⚠️ Suba previa de precio detectada</span>" if hist.has_recent_price_increase else ""
            history_html = f"""
            <div class='history-box'>
                📈 <strong>Historial 30 días:</strong> Promedio anterior: ${hist.avg_price:,.2f} | Mínimo: ${hist.min_price:,.2f}
                <br>Descuento vs promedio histórico: <strong>{hist.historical_discount_percent}%</strong>{warning_tag}
            </div>
            """

        deals_html += f"""
        <div class="deal-card">
            {image_html}
            <div class="deal-content">
                <p class="store-name">{deal.store}</p>
                <h3 class="deal-title"><a href="{deal.product_link}" target="_blank">{deal.title}</a></h3>
                <div class="price-container">
                    <span class="current-price">${deal.current_price:,.2f}</span>
                    {prev_price_html}
                    {discount_badge}
                </div>
                {market_html}
                {history_html}
            </div>
        </div>
        """

    # Rejected items section
    rejected_html = ""
    if rejected_deals:
        rows_html = ""
        for item in rejected_deals:
            d = item.deal
            price_text = f"${d.current_price:,.2f}" if d.current_price else "N/A"
            disc_text = f" <span style='color: #888;'>({d.discount_percent}% OFF)</span>" if d.discount_percent else ""
            link_start = f"<a href='{d.product_link}' target='_blank' style='color: #495057; text-decoration: none; font-weight: 500;'>" if d.product_link else ""
            link_end = "</a>" if d.product_link else ""

            rows_html += f"""
            <tr>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e9ecef; vertical-align: top;">
                    <div style="font-weight: bold; color: #2c3e50; font-size: 11px;">{d.store}</div>
                    <div style="color: #28a745; font-size: 12px; font-weight: 600;">{price_text}{disc_text}</div>
                </td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e9ecef; vertical-align: top; font-size: 12px;">
                    {link_start}{d.title}{link_end}
                </td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e9ecef; vertical-align: top;">
                    <span class="reject-tag" style="word-break: break-all;">{item.reason}</span>
                </td>
            </tr>
            """

        rejected_html = f"""
        <div class="rejected-wrapper">
            <div class="rejected-header">
                <h3>🚫 Artículos Analizados y Rechazados ({len(rejected_deals)})</h3>
                <p style="margin: 4px 0 0 0; color: #6c757d; font-size: 12px;">Listado de publicaciones evaluadas que no cumplieron los criterios de selección.</p>
            </div>
            <table class="rejected-table">
                <thead>
                    <tr>
                        <th style="width: 25%;">Tienda / Precio</th>
                        <th style="width: 45%;">Producto</th>
                        <th style="width: 30%;">Causa de Rechazo</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #f4f4f7;
                color: #333333;
                margin: 0;
                padding: 0;
            }}
            .email-wrapper {{
                max-width: 680px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #eaeaea;
                padding-bottom: 15px;
                margin-bottom: 20px;
            }}
            .header h1 {{
                color: #2c3e50;
                font-size: 24px;
                margin: 0;
            }}
            .deal-card {{
                display: flex;
                flex-direction: row;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                margin-bottom: 15px;
                padding: 14px;
                background-color: #fff;
                align-items: flex-start;
            }}
            .deal-img {{
                width: 80px;
                height: 80px;
                object-fit: contain;
                margin-right: 15px;
                border-radius: 4px;
                border: 1px solid #eee;
            }}
            .deal-content {{
                flex: 1;
            }}
            .store-name {{
                font-size: 12px;
                text-transform: uppercase;
                color: #6c757d;
                margin: 0 0 4px 0;
                font-weight: 600;
            }}
            .deal-title {{
                font-size: 14px;
                margin: 0 0 8px 0;
                line-height: 1.4;
            }}
            .deal-title a {{
                color: #0366d6;
                text-decoration: none;
            }}
            .deal-title a:hover {{
                text-decoration: underline;
            }}
            .price-container {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 8px;
            }}
            .current-price {{
                font-size: 16px;
                font-weight: bold;
                color: #28a745;
            }}
            .old-price {{
                font-size: 13px;
                text-decoration: line-through;
                color: #6c757d;
            }}
            .badge {{
                background-color: #dc3545;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 4px;
            }}
            .market-comparison {{
                font-size: 12px;
                padding: 6px 8px;
                border-radius: 4px;
                background-color: #f8f9fa;
                border-left: 3px solid #6c757d;
                margin-bottom: 6px;
            }}
            .market-cheaper {{
                background-color: #e8f5e9;
                border-left-color: #28a745;
                color: #1b5e20;
            }}
            .market-warning {{
                background-color: #fff3e0;
                border-left-color: #ff9800;
                color: #e65100;
            }}
            .market-neutral {{
                background-color: #f1f3f5;
                border-left-color: #adb5bd;
                color: #6c757d;
            }}
            .history-box {{
                font-size: 11px;
                padding: 6px 8px;
                background-color: #f0f4f8;
                border-radius: 4px;
                color: #495057;
            }}
            .rejected-wrapper {{
                margin-top: 25px;
                border-top: 2px dashed #e1e4e8;
                padding-top: 15px;
            }}
            .rejected-header h3 {{
                font-size: 15px;
                color: #495057;
                margin: 0;
            }}
            .rejected-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                font-size: 12px;
            }}
            .rejected-table th {{
                background-color: #f8f9fa;
                color: #495057;
                text-align: left;
                padding: 7px 10px;
                border-bottom: 2px solid #dee2e6;
                font-size: 11px;
                text-transform: uppercase;
            }}
            .rejected-table tr:nth-child(even) {{
                background-color: #fafbfc;
            }}
            .reject-tag {{
                display: inline-block;
                background-color: #fff5f5;
                color: #c53030;
                border: 1px solid #feb2b2;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }}
            .footer {{
                text-align: center;
                font-size: 12px;
                color: #8c959f;
                margin-top: 30px;
                border-top: 1px solid #eaeaea;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                <h1>🔥 HardGamers Top Deals & Price Check</h1>
                <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 14px;">Reporte diario de ofertas con validación de precios frente a la competencia e historial de 30 días.</p>
            </div>
            <div class="deals-list">
                {deals_html if deals else "<p style='text-align: center; color: #6c757d;'>No se encontraron ofertas que superen los filtros seleccionados.</p>"}
            </div>
            {rejected_html}
            <div class="footer">
                <p>Automated HardGamers Deal Alert Agent. Happy Gaming!</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email_alert(deals: List[Deal], rejected_deals: Optional[List[RejectedDeal]] = None) -> bool:
    """Send the email alert with the given deals and rejected items via SMTP."""
    if not deals and not rejected_deals:
        logger.info("No deals or rejected items to send via email.")
        return True

    if not config.is_email_configured():
        logger.info("Configuración SMTP no provista o incompleta. Envío de email omitido.")
        return True

    deals_count_str = f"{len(deals)} Ofertas Verificadas" if deals else "Reporte de Análisis"
    subject = f"🔥 HardGamers Alert: {deals_count_str}!"
    html_body = generate_html_email(deals, rejected_deals=rejected_deals)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM or config.SMTP_USER
    msg["To"] = config.EMAIL_TO

    msg.attach(MIMEText(html_body, "html"))

    recipients = [email.strip() for email in config.EMAIL_TO.split(",")]

    try:
        logger.info(f"Connecting to SMTP server {config.SMTP_SERVER}:{config.SMTP_PORT}...")
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(msg["From"], recipients, msg.as_string())
        logger.info(f"Email alert successfully sent to {config.EMAIL_TO}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False
