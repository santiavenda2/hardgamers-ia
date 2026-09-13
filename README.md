# HardGamers Deals Scraper

Script en Python diseñado para monitorear la sección de ofertas ("deals") de [HardGamers](https://www.hardgamers.com.ar/deals), analizar las publicaciones para identificar ofertas reales frente a la competencia e historial de precios de 30 días, y enviar un reporte periódico por correo electrónico o consultar los resultados en consola.

## Requisitos Técnicos

*   **Lenguaje:** Python 3.14+
*   **Gestor de Proyecto y Entorno:** `uv` (especificado en `pyproject.toml`)
*   **Librerías principales:**
    *   `requests`: Para realizar peticiones HTTP.
    *   `beautifulsoup4`: Para el parseo de HTML.
    *   `smtplib`: Para el envío de mails (incluido en Python).

## Arquitectura del Proyecto

*   `scraper.py`: Realiza las solicitudes HTTP (`safe_get`) con manejo automático de *rate limiting* (HTTP 429), lectura de cabeceras `Retry-After` / `X-Ratelimit-Reset` y backoff inteligente. 
    * **Optimización de paginación temprana (*early exit*):** Dado que HardGamers entrega las ofertas ordenadas de mayor a menor descuento, el scraper interrumpe la recolección en cuanto encuentra un producto con un descuento menor al umbral configurado (`min_discount`), evitando peticiones HTTP innecesarias.
    * Extrae datos del producto, historial de precios a 30 días y búsqueda de competidores con enlaces directos.
*   `analyzer.py`: Lógica para filtrar las ofertas y detectar oportunidades reales. Realiza la validación profunda (competencia e historial de 30 días) de manera secuencial con pausas configurables para evitar sobrecargar la plataforma. Descarta automáticamente ofertas si la diferencia de precio frente a la competencia más barata no supera el 10%.
*   `notifier.py`: Genera el cuerpo del email en formato HTML con la lista de ofertas seleccionadas, enlaces de búsqueda y a la competencia, y realiza el envío por SMTP.
*   `main.py`: Orquestador que ejecuta el proceso completo de forma secuencial.
*   `config.py`: Almacena credenciales SMTP y parámetros de configuración con lectura segura de variables de entorno.

## Instalación y Configuración Local

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

Opciones disponibles en CLI:
* `--max-pages`: Número máximo de páginas de ofertas a scrapear (por defecto: 10, con interrupción temprana automática al caer por debajo de `--min-discount`).
* `--min-discount`: Porcentaje mínimo de descuento en tienda (por defecto: 20%).
* `--min-competitor-discount`: Porcentaje mínimo de reducción requerido frente al vendedor competidor más barato (por defecto: 10%).
* `--min-price-drop`: Rebaja mínima absoluta en ARS.
* `--max-deals-to-validate`: Cantidad máxima de ofertas principales a validar profundamente en la red.
* `--delay`: Tiempo de espera (en segundos) entre validaciones de artículos (por defecto: 1.5s).
* `--include` / `--exclude`: Filtros de texto por nombre de producto.
* `--sort-by`: `discount`, `market_discount`, `price_drop`, `price_asc`.
* `--no-email`: Ejecutar en modo *dry-run* (solo consola).

---

## Automatización con GitHub Actions

El repositorio incluye un flujo de trabajo automatizado en `.github/workflows/scanner.yml`:

* **Ejecución Programada (Cron):** Se ejecuta dos veces al día de forma automática (a las 12:00 UTC y 21:00 UTC).
* **Ejecución Manual (Workflow Dispatch):** Permite disparar el análisis manualmente desde la pestaña *Actions* de GitHub, con parámetros configurables (`min_discount`, `max_deals`, `delay`, `send_email`).

### Configuración de Secretos en GitHub

Para recibir las notificaciones por email en GitHub Actions, configura los siguientes **Repository Secrets** en `Settings > Secrets and variables > Actions`:

| Secreto | Descripción | Ejemplo |
|---|---|---|
| `SMTP_SERVER` | Servidor SMTP | `smtp.gmail.com` |
| `SMTP_PORT` | Puerto SMTP | `587` |
| `SMTP_USER` | Usuario / Email remitente | `tu_usuario@gmail.com` |
| `SMTP_PASSWORD` | Contraseña de aplicación SMTP | `xxxx xxxx xxxx xxxx` |
| `EMAIL_FROM` | Dirección de envío visible (opcional) | `tu_usuario@gmail.com` |
| `EMAIL_TO` | Destinatario(s) (separados por coma) | `destinatario@example.com` |
