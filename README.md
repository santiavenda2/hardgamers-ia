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

*   `scraper.py`: Realiza las solicitudes HTTP y extrae la información de los productos en la sección de Deals (título, tienda, precio actual, precio de lista/anterior, link, imagen).
*   `analyzer.py`: Lógica para filtrar las ofertas y detectar cuáles son efectivamente oportunidades reales basadas en reglas definidas. Incluye validación de mercado y análisis de historial de precios.
*   `notifier.py`: Genera el cuerpo del email en formato HTML con la lista de ofertas seleccionadas y realiza el envío por SMTP.
*   `main.py`: Orquestador que ejecuta el proceso completo de forma secuencial.
*   `config.py`: Almacena credenciales SMTP y parámetros de configuración (por ejemplo, el porcentaje mínimo de descuento para reportar).

## Instalación y Configuración

El proyecto está gestionado con [uv](https://github.com/astral-sh/uv).

1. Sincronizar el entorno e instalar dependencias:
   ```bash
   uv sync
   ```

2. Configurar variables de entorno (SMTP_SERVER, SMTP_USER, SMTP_PASSWORD, EMAIL_TO, etc.) para el envío de notificaciones.

## Ejemplos de Uso

Ejecución básica (solo consola):
```bash
uv run main.py --no-email
```

Buscar solo monitores LG y excluir switches (con validación de mercado):
```bash
uv run main.py --include "monitor,lg" --exclude "switch" --sort-by market_discount
```

Ejecución diaria programada (validando solo las 15 mejores ofertas para evitar límites de API):
```bash
uv run main.py --min-discount 30 --max-deals-to-validate 15 --sort-by market_discount
```

Opciones disponibles:
* `--max-pages`: Número de páginas a scrapear.
* `--min-discount`: Porcentaje mínimo de descuento.
* `--include` / `--exclude`: Filtros de texto por nombre de producto.
* `--sort-by`: `discount`, `market_discount`, `price_drop`, `price_asc`.
* `--no-email`: Ejecutar en modo *dry-run* (solo consola).
