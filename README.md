# HardGamers Deals Scraper

Script en Python diseñado para monitorear la sección de ofertas ("deals") de [HardGamers](https://www.hardgamers.com.ar/deals), analizar las publicaciones para identificar ofertas reales y enviar un reporte diario por correo electrónico.

## Requisitos Técnicos

*   **Lenguaje:** Python 3.14+
*   **Gestor de Proyecto y Entorno:** `uv` (especificado en `pyproject.toml`)
*   **Librerías principales:**
    *   `requests`: Para realizar peticiones HTTP.
    *   `beautifulsoup4`: Para el parseo de HTML.
    *   `smtplib`: Para el envío de mails (incluido en Python).

## Arquitectura del Proyecto

*   `scraper.py`: Realiza las solicitudes HTTP (`safe_get`) con manejo automático de *rate limiting* (HTTP 429), lectura de cabeceras `Retry-After` / `X-Ratelimit-Reset` y backoff inteligente. Extrae información de deals, competidores e historial de precios.
*   `analyzer.py`: Lógica para filtrar las ofertas y detectar oportunidades reales. Realiza la validación profunda (competencia e historial de 30 días) de manera secuencial con pausas configurables para evitar sobrecargar la plataforma.
*   `notifier.py`: Genera el cuerpo del email en formato HTML con la lista de ofertas seleccionadas y realiza el envío por SMTP.
*   `main.py`: Orquestador que ejecuta el proceso completo de forma secuencial.
*   `config.py`: Almacena credenciales SMTP y parámetros de configuración (delay entre peticiones, porcentaje mínimo de descuento, etc.).

## Instalación y Configuración

El proyecto está gestionado con [uv](https://github.com/astral-sh/uv).

1. Sincronizar el entorno e instalar dependencias:
   ```bash
   uv sync
   ```

2. Configurar variables de entorno (`SMTP_SERVER`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, `REQUEST_DELAY_SECONDS`, etc.) según corresponda.

## Ejemplos de Uso

Ejecución básica (solo consola, validando Top 20):
```bash
uv run python main.py --no-email --max-deals-to-validate 20
```

Personalizar el tiempo de espera entre análisis de artículos:
```bash
uv run python main.py --delay 2.0 --max-deals-to-validate 30
```

Buscar solo monitores LG y excluir switches (con validación de mercado):
```bash
uv run python main.py --include "monitor,lg" --exclude "switch" --sort-by market_discount
```

Opciones disponibles:
* `--max-pages`: Número de páginas de ofertas a scrapear (por defecto: 1).
* `--min-discount`: Porcentaje mínimo de descuento en tienda (por defecto: 30%).
* `--min-price-drop`: Rebaja mínima absoluta en ARS.
* `--max-deals-to-validate`: Cantidad máxima de ofertas principales a validar profundamente en la red.
* `--delay`: Tiempo de espera (en segundos) entre validaciones de artículos (por defecto: 1.5s).
* `--include` / `--exclude`: Filtros de texto por nombre de producto.
* `--sort-by`: `discount`, `market_discount`, `price_drop`, `price_asc`.
* `--no-email`: Ejecutar en modo *dry-run* (solo consola).
