import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import List
from scraper import Deal
import config

logger = logging.getLogger(__name__)

def generate_html_email(deals: List[Deal]) -> str:
    """Generate a clean, responsive HTML email body with the list of deals, market comparison & 30-day history."""
    deals_html = ""
    for deal in deals:
        prev_price_html = f"<span class='old-price'>${deal.previous_price:,.2f}</span>" if deal.previous_price else ""
        discount_badge = f"<span class='badge'>{deal.discount_percent}% OFF</span>" if deal.discount_percent else ""
        image_html = f"<img src='{deal.image_url}' alt='{deal.title}' class='deal-img'>" if deal.image_url else ""
        
        # Competitor validation block
        if deal.similar_found and deal.competitors:
            best_comp = deal.competitors[0]
            if deal.is_truly_cheaper and deal.market_discount_percent and deal.market_discount_percent > 0:
                market_html = f"""
                <div class='market-comparison market-cheaper'>
                    ✅ <strong>¡Más barato que la competencia!</strong> {deal.market_discount_percent}% menos que <strong>{best_comp['store']}</strong> (${best_comp['price']:,.2f})
                </div>
                """
            elif deal.market_discount_percent is not None and deal.market_discount_percent <= 0:
                market_html = f"""
                <div class='market-comparison market-warning'>
                    ⚠️ Encontrado más barato o igual en <strong>{best_comp['store']}</strong> (${best_comp['price']:,.2f})
                </div>
                """
            else:
                market_html = f"""
                <div class='market-comparison'>
                    📊 Competidor más cercano: <strong>{best_comp['store']}</strong> (${best_comp['price']:,.2f})
                </div>
                """
        else:
            market_html = """
            <div class='market-comparison market-neutral'>
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
                max-width: 650px;
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
                {deals_html}
            </div>
            <div class="footer">
                <p>Automated HardGamers Deal Alert Agent. Happy Gaming!</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email_alert(deals: List[Deal]) -> bool:
    """Send the email alert with the given deals via SMTP."""
    if not deals:
        logger.info("No deals to send via email.")
        return True

    if not config.SMTP_USER or not config.SMTP_PASSWORD or not config.EMAIL_TO:
        logger.warning("SMTP credentials or recipient email are not configured. Skipping email send.")
        return False

    subject = f"🔥 HardGamers Alert: {len(deals)} Ofertas Verificadas!"
    html_body = generate_html_email(deals)

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
