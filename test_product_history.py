import requests
from bs4 import BeautifulSoup
import json
import re

def inspect_product_page(product_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    print(f"Fetching {product_url}...")
    resp = requests.get(product_url, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Check for canvas/chart or script tags containing price history data
    scripts = soup.find_all("script")
    print(f"Found {len(scripts)} scripts.")
    
    for i, s in enumerate(scripts):
        text = s.get_text()
        if "history" in text.lower() or "chart" in text.lower() or "price" in text.lower() or "labels" in text.lower():
            print(f"\n--- Relevant Script {i} ---")
            print(text[:1500])
            
    # Check for canvas elements or elements with price history
    canvases = soup.find_all(["canvas", "div", "section"], class_=lambda c: c and ("chart" in c.lower() or "history" in c.lower() or "price" in c.lower()))
    print(f"\nFound {len(canvases)} relevant DOM elements:")
    for c in canvases[:5]:
        print(f"Tag: <{c.name}> class={c.get('class')} id={c.get('id')}")

if __name__ == "__main__":
    # Test with one of the deals we scraped
    inspect_product_page("https://www.hardgamers.com.ar/product/black:203378")
