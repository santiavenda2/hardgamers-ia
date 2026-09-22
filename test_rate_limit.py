import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
from hardgamers_scraper import parse_discount
from models import Deal


def run_limited_test():
    url = "https://www.hardgamers.com.ar/deals?page=1&limit=54"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    articles = soup.find_all("article", class_="One-Bit-Product")
    
    deals = []
    for art in articles:
        name_el = art.find("p", class_="product-name")
        title = name_el.get_text(strip=True) if name_el else ""
        store_el = art.find("p", class_="store")
        store = store_el.get_text(strip=True) if store_el else ""
        offer_el = art.find("div", class_="offer")
        disc = parse_discount(offer_el.get_text(strip=True)) if offer_el else None
        
        img_container = art.find("a", class_="img-container")
        href = img_container.get("href") if img_container else ""
        product_link = f"https://www.hardgamers.com.ar{href}" if href.startswith("/") else href

        deals.append(Deal(title=title, store=store, current_price=100.0, previous_price=200.0, discount_percent=disc, product_link=product_link, image_url=""))

    print(f"Total ofertas colectadas de la página: {len(deals)}")
    
    # Probar hasta 25 solicitudes secuenciales midiendo tiempo y detección de 429
    processed = 0
    stopped_at = None
    
    for i, d in enumerate(deals[:30], 1):
        tokens = [w for w in re.findall(r'[A-Za-z0-9]+', d.title.upper()) if len(w) > 1 or w.isdigit()]
        query = ' '.join(tokens[:5])
        s_url = f"https://www.hardgamers.com.ar/search?text={urllib.parse.quote(query)}"
        
        try:
            r = requests.get(s_url, headers=headers, timeout=2)
            if r.status_code == 429:
                print(f"--> [429 ERROR] en petición #{i}")
                stopped_at = i
                break
            elif r.status_code == 200:
                processed += 1
                print(f"#{i} OK", end=" ", flush=True)
            else:
                print(f"#{i} HTTP {r.status_code}", end=" ", flush=True)
        except Exception as e:
            print(f"#{i} Timeout/Err", end=" ", flush=True)
            
    print(f"\n\nProcesadas con éxito: {processed}")
    if stopped_at:
        print(f"Límite 429 alcanzado en petición #{stopped_at}")

    print("\n" + "="*80)
    print("RESULTADOS Y ESTRATEGIAS DE FILTRADO PARA PREVENIR EL 429:")
    print("="*80)
    
    discounts = [d.discount_percent for d in deals if d.discount_percent is not None]
    print(f"Total ofertas recibidas en HardGamers deals: {len(deals)}")
    
    print("\n1. Estrategia por Descuento Mínimo en Tienda:")
    for threshold in [25, 30, 35, 40]:
        matching = [d for d in deals if d.discount_percent and d.discount_percent >= threshold]
        pct = (len(matching) / len(deals)) * 100
        print(f"   - Descuento >= {threshold}%: reduce de {len(deals)} a {len(matching)} ofertas (Ahorra {100-pct:.1f}% de las peticiones)")

    print("\n2. Estrategia por Límite de Peticiones Máximas (max_deals_to_validate):")
    for n in [10, 15, 20]:
        print(f"   - Validar solo Top {n} ofertas: reduce de {len(deals)} a {n} peticiones (Ahorra {100 - (n/len(deals)*100):.1f}% de las peticiones)")

if __name__ == "__main__":
    run_limited_test()
