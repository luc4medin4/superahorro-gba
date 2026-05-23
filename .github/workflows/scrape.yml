"""
scraper.py — SuperAhorro GBA
Scraper de ofertas de supermercados para zona norte GBA.
Corre diariamente via GitHub Actions.
"""

import json
import os
import re
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# ─── Configuración ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Zona horaria Argentina
TZ_AR = timezone(timedelta(hours=-3))
AHORA = datetime.now(TZ_AR)
FECHA_HOY = AHORA.strftime("%Y-%m-%d")
FECHA_HORA = AHORA.strftime("%Y-%m-%dT%H:%M:%S-03:00")

# Directorio de salida
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = DATA_DIR / "ofertas.json"

# Headers base con user-agent rotado
try:
    UA = UserAgent()
except Exception:
    UA = None

HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}

DELAY_ENTRE_REQUESTS = 3  # segundos entre requests al mismo dominio
TIMEOUT = 20

todas_las_ofertas: list[dict] = []


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_ua() -> str:
    try:
        return UA.random if UA else "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36"
    except Exception:
        return "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36"


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS_BASE)
    s.headers["User-Agent"] = get_ua()
    return s


def safe_get(session: requests.Session, url: str, **kwargs) -> Optional[requests.Response]:
    try:
        r = session.get(url, timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except requests.exceptions.HTTPError as e:
        log.warning(f"HTTP {e.response.status_code} en {url}")
    except requests.exceptions.ConnectionError:
        log.warning(f"Sin conexión a {url}")
    except requests.exceptions.Timeout:
        log.warning(f"Timeout en {url}")
    except Exception as e:
        log.warning(f"Error inesperado en {url}: {e}")
    return None


def limpiar_precio(texto: str) -> Optional[float]:
    """Extrae número flotante de un string de precio."""
    if not texto:
        return None
    limpio = re.sub(r"[^\d,.]", "", texto.strip())
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return round(float(limpio), 2)
    except ValueError:
        return None


def calcular_descuento(precio: float, precio_anterior: float) -> Optional[float]:
    if precio and precio_anterior and precio_anterior > precio:
        return round((1 - precio / precio_anterior) * 100, 1)
    return None


def oferta(
    producto: str,
    precio: float,
    supermercado: str,
    url: str,
    precio_anterior: float = None,
    imagen_url: str = None,
    categoria: str = "general",
    sucursal: str = None,
    vencimiento: str = None,
) -> dict:
    descuento = calcular_descuento(precio, precio_anterior)
    return {
        "producto": producto.strip()[:200],
        "precio": precio,
        "precio_anterior": precio_anterior,
        "descuento_pct": descuento,
        "supermercado": supermercado,
        "sucursal": sucursal,
        "categoria": categoria,
        "fecha_scrape": FECHA_HOY,
        "fecha_vencimiento": vencimiento,
        "url_fuente": url,
        "imagen_url": imagen_url,
    }


# ─── Scrapers por supermercado ─────────────────────────────────────────────────

def scrape_carrefour() -> list[dict]:
    """
    Carrefour Argentina — carrefour.com.ar
    Scrapea la página de promociones/ofertas.
    """
    log.info("🔵 Scrapeando Carrefour...")
    resultados = []
    session = make_session()

    urls = [
        "https://www.carrefour.com.ar/supermercado",
        "https://www.carrefour.com.ar/ofertas",
    ]

    for url in urls:
        r = safe_get(session, url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # Carrefour usa una SPA (React), buscar datos en JSON embebido
        scripts = soup.find_all("script", {"type": "application/json"})
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                # Intentar extraer productos del JSON de Next.js / Vtex
                productos = _extraer_vtex_productos(data)
                resultados.extend(productos)
            except Exception:
                pass

        # Fallback: buscar tarjetas de producto en HTML
        tarjetas = soup.select(".valtech-carrefourar-product-summary-2-x-container, .vtex-product-summary")
        for t in tarjetas[:30]:
            nombre_el = t.select_one(".vtex-product-summary-2-x-productBrand, h3")
            precio_el = t.select_one(".carrefourar-store-components-0-x-sellingPriceValue, .sellingPrice")
            precio_ant_el = t.select_one(".carrefourar-store-components-0-x-listPriceValue, .listPrice")
            img_el = t.select_one("img")
            link_el = t.select_one("a")

            if not nombre_el or not precio_el:
                continue

            precio = limpiar_precio(precio_el.get_text())
            precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

            if not precio:
                continue

            resultados.append(oferta(
                producto=nombre_el.get_text(),
                precio=precio,
                precio_anterior=precio_ant,
                supermercado="Carrefour",
                url=url,
                imagen_url=img_el.get("src") if img_el else None,
            ))

        time.sleep(DELAY_ENTRE_REQUESTS)

    log.info(f"  → {len(resultados)} ofertas de Carrefour")
    return resultados


def _extraer_vtex_productos(data: dict | list) -> list[dict]:
    """Intenta extraer productos de JSON de Vtex/Next.js embebido."""
    resultados = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("products", "items") and isinstance(value, list):
                for item in value[:20]:
                    try:
                        nombre = item.get("productName") or item.get("name", "")
                        sellers = item.get("items", [{}])[0].get("sellers", [{}])
                        precio = sellers[0].get("commertialOffer", {}).get("Price")
                        precio_ant = sellers[0].get("commertialOffer", {}).get("ListPrice")
                        if nombre and precio:
                            resultados.append(oferta(
                                producto=nombre,
                                precio=float(precio),
                                precio_anterior=float(precio_ant) if precio_ant else None,
                                supermercado="Carrefour",
                                url="https://www.carrefour.com.ar",
                            ))
                    except Exception:
                        pass
            elif isinstance(value, (dict, list)):
                resultados.extend(_extraer_vtex_productos(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                resultados.extend(_extraer_vtex_productos(item))
    return resultados[:30]


def scrape_dia() -> list[dict]:
    """
    Supermercados Día — diaonline.supermercadosdia.com.ar
    """
    log.info("🔴 Scrapeando Día...")
    resultados = []
    session = make_session()

    urls = [
        "https://diaonline.supermercadosdia.com.ar/ofertas",
        "https://diaonline.supermercadosdia.com.ar/promociones",
    ]

    for url in urls:
        r = safe_get(session, url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # Día usa Vtex también
        tarjetas = soup.select(".vtex-product-summary-2-x-container, .shelf-item")
        for t in tarjetas[:30]:
            nombre_el = t.select_one(".vtex-product-summary-2-x-productBrand, .shelf-item__title")
            precio_el = t.select_one(".dia-online-store-theme-1-x-sellingPriceValue, .shelf-item__price")
            precio_ant_el = t.select_one(".dia-online-store-theme-1-x-listPriceValue")
            img_el = t.select_one("img")

            if not nombre_el or not precio_el:
                continue

            precio = limpiar_precio(precio_el.get_text())
            precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

            if not precio:
                continue

            resultados.append(oferta(
                producto=nombre_el.get_text(),
                precio=precio,
                precio_anterior=precio_ant,
                supermercado="Día",
                url=url,
                imagen_url=img_el.get("src") if img_el else None,
            ))

        time.sleep(DELAY_ENTRE_REQUESTS)

    log.info(f"  → {len(resultados)} ofertas de Día")
    return resultados


def scrape_coto() -> list[dict]:
    """
    Coto Digital — cotodigital.com.ar
    """
    log.info("🟡 Scrapeando Coto...")
    resultados = []
    session = make_session()
    session.headers["Referer"] = "https://www.cotodigital.com.ar/"

    url = "https://www.cotodigital.com.ar/sitios/cdigi/promociones"
    r = safe_get(session, url)
    if not r:
        log.warning("  → Coto no respondió")
        return []

    soup = BeautifulSoup(r.text, "lxml")

    tarjetas = soup.select(".product-card, .catalogEntryContentCell, .grid-item")
    for t in tarjetas[:30]:
        nombre_el = t.select_one(".product-name, .description, h3, h4")
        precio_el = t.select_one(".atg_store_newPrice, .price-value, .product-price")
        precio_ant_el = t.select_one(".atg_store_oldPrice, .price-old")
        img_el = t.select_one("img")

        if not nombre_el or not precio_el:
            continue

        precio = limpiar_precio(precio_el.get_text())
        precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

        if not precio:
            continue

        resultados.append(oferta(
            producto=nombre_el.get_text(),
            precio=precio,
            precio_anterior=precio_ant,
            supermercado="Coto",
            url=url,
            imagen_url=img_el.get("src") if img_el else None,
        ))

    log.info(f"  → {len(resultados)} ofertas de Coto")
    return resultados


def scrape_changomas() -> list[dict]:
    """
    Changomas / MasOnline — masonline.com.ar
    """
    log.info("🟢 Scrapeando Changomas...")
    resultados = []
    session = make_session()

    urls = [
        "https://www.masonline.com.ar/ofertas",
        "https://www.masonline.com.ar/supermercado",
    ]

    for url in urls:
        r = safe_get(session, url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # MasOnline también usa Vtex
        tarjetas = soup.select(".vtex-product-summary-2-x-container")
        for t in tarjetas[:30]:
            nombre_el = t.select_one(".vtex-product-summary-2-x-productBrand")
            precio_el = t.select_one("[class*='sellingPriceValue']")
            precio_ant_el = t.select_one("[class*='listPriceValue']")
            img_el = t.select_one("img")

            if not nombre_el or not precio_el:
                continue

            precio = limpiar_precio(precio_el.get_text())
            precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

            if not precio:
                continue

            resultados.append(oferta(
                producto=nombre_el.get_text(),
                precio=precio,
                precio_anterior=precio_ant,
                supermercado="Changomas",
                url=url,
                imagen_url=img_el.get("src") if img_el else None,
            ))

        time.sleep(DELAY_ENTRE_REQUESTS)

    log.info(f"  → {len(resultados)} ofertas de Changomas")
    return resultados


def scrape_vea_jumbo_disco() -> list[dict]:
    """
    Cencosud: Vea, Jumbo, Disco — via Jumbo.com.ar y Vea.com.ar
    """
    log.info("🔵 Scrapeando Cencosud (Jumbo/Vea/Disco)...")
    resultados = []
    session = make_session()

    fuentes = [
        ("Jumbo", "https://www.jumbo.com.ar/ofertas"),
        ("Vea", "https://www.vea.com.ar/ofertas"),
        ("Disco", "https://www.disco.com.ar/ofertas"),
    ]

    for nombre_super, url in fuentes:
        r = safe_get(session, url)
        if not r:
            log.warning(f"  → {nombre_super} no respondió")
            continue

        soup = BeautifulSoup(r.text, "lxml")

        tarjetas = soup.select(".vtex-product-summary-2-x-container, .product-card")
        for t in tarjetas[:20]:
            nombre_el = t.select_one(".vtex-product-summary-2-x-productBrand, h3")
            precio_el = t.select_one("[class*='sellingPriceValue'], .price")
            precio_ant_el = t.select_one("[class*='listPriceValue'], .old-price")
            img_el = t.select_one("img")

            if not nombre_el or not precio_el:
                continue

            precio = limpiar_precio(precio_el.get_text())
            precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

            if not precio:
                continue

            resultados.append(oferta(
                producto=nombre_el.get_text(),
                precio=precio,
                precio_anterior=precio_ant,
                supermercado=nombre_super,
                url=url,
                imagen_url=img_el.get("src") if img_el else None,
            ))

        time.sleep(DELAY_ENTRE_REQUESTS)

    log.info(f"  → {len(resultados)} ofertas de Cencosud")
    return resultados


def scrape_maxiconsumo() -> list[dict]:
    """
    Maxiconsumo — maxiconsumo.com
    Mayorista, precios por mayor.
    """
    log.info("🟤 Scrapeando Maxiconsumo...")
    resultados = []
    session = make_session()

    url = "https://www.maxiconsumo.com/ofertas-especiales"
    r = safe_get(session, url)
    if not r:
        log.warning("  → Maxiconsumo no respondió")
        return []

    soup = BeautifulSoup(r.text, "lxml")

    tarjetas = soup.select(".product-item, .item, article")
    for t in tarjetas[:30]:
        nombre_el = t.select_one(".product-item-name, .product-name, h2, h3")
        precio_el = t.select_one(".price, .special-price .price")
        precio_ant_el = t.select_one(".old-price .price, .regular-price")
        img_el = t.select_one("img")

        if not nombre_el or not precio_el:
            continue

        precio = limpiar_precio(precio_el.get_text())
        precio_ant = limpiar_precio(precio_ant_el.get_text()) if precio_ant_el else None

        if not precio:
            continue

        resultados.append(oferta(
            producto=nombre_el.get_text(),
            precio=precio,
            precio_anterior=precio_ant,
            supermercado="Maxiconsumo",
            url=url,
            imagen_url=img_el.get("src") if img_el else None,
            categoria="mayorista",
        ))

    log.info(f"  → {len(resultados)} ofertas de Maxiconsumo")
    return resultados


def scrape_diarco() -> list[dict]:
    """
    Diarco — diarco.com.ar
    """
    log.info("🟣 Scrapeando Diarco...")
    resultados = []
    session = make_session()

    url = "https://www.diarco.com.ar/ofertas"
    r = safe_get(session, url)
    if not r:
        log.warning("  → Diarco no respondió")
        return []

    soup = BeautifulSoup(r.text, "lxml")

    tarjetas = soup.select(".product-card, .product, article, .item")
    for t in tarjetas[:30]:
        nombre_el = t.select_one("h2, h3, h4, .title, .name")
        precio_el = t.select_one(".price, .product-price, [class*='price']")
        img_el = t.select_one("img")

        if not nombre_el or not precio_el:
            continue

        precio = limpiar_precio(precio_el.get_text())
        if not precio:
            continue

        resultados.append(oferta(
            producto=nombre_el.get_text(),
            precio=precio,
            supermercado="Diarco",
            url=url,
            imagen_url=img_el.get("src") if img_el else None,
            categoria="mayorista",
        ))

    log.info(f"  → {len(resultados)} ofertas de Diarco")
    return resultados


# ─── Búsqueda en redes sociales vía Google ─────────────────────────────────────
# ⚠️ FRÁGIL: Google puede bloquear requests automatizados.
# Esta sección puede fallar sin romper el resto del scraper.

def buscar_redes_sociales() -> list[dict]:
    """
    Intenta encontrar ofertas en redes sociales buscando en Google/Bing.
    FRÁGIL — puede fallar en cualquier momento.
    """
    log.info("📱 Buscando en redes sociales (búsquedas web)...")
    resultados = []
    session = make_session()
    session.headers["User-Agent"] = get_ua()

    supermercados_queries = [
        ("Carrefour", "carrefour jose c paz ofertas semana"),
        ("Día", "supermercados dia jose c paz promociones"),
        ("Coto", "coto supermercado jose c paz ofertas"),
        ("Changomas", "changomas ofertas norte gba"),
    ]

    for super_nombre, query in supermercados_queries:
        try:
            # Búsqueda en Bing (menos restrictivo que Google para bots)
            url = f"https://www.bing.com/search?q={query.replace(' ', '+')}&freshness=Week"
            r = safe_get(session, url)
            if not r:
                time.sleep(5)
                continue

            soup = BeautifulSoup(r.text, "lxml")

            # Extraer snippets de resultados de búsqueda
            snippets = soup.select(".b_algo")
            for snippet in snippets[:3]:
                titulo_el = snippet.select_one("h2")
                desc_el = snippet.select_one(".b_caption p")
                link_el = snippet.select_one("a")

                if not titulo_el:
                    continue

                titulo = titulo_el.get_text(strip=True)
                desc = desc_el.get_text(strip=True) if desc_el else ""
                link = link_el.get("href") if link_el else ""

                # Solo incluir si menciona precios o descuentos
                texto_completo = f"{titulo} {desc}".lower()
                if any(kw in texto_completo for kw in ["%", "off", "descuento", "promo", "$", "oferta"]):
                    resultados.append({
                        "producto": titulo[:150],
                        "precio": None,
                        "precio_anterior": None,
                        "descuento_pct": None,
                        "supermercado": super_nombre,
                        "sucursal": None,
                        "categoria": "red_social",
                        "fecha_scrape": FECHA_HOY,
                        "fecha_vencimiento": None,
                        "url_fuente": link,
                        "imagen_url": None,
                        "descripcion": desc[:300],
                    })

            time.sleep(10)  # Rate limit alto para no banear
        except Exception as e:
            log.warning(f"  → Error buscando redes para {super_nombre}: {e}")

    log.info(f"  → {len(resultados)} resultados de redes sociales (aprox.)")
    return resultados


# ─── Categorización automática ────────────────────────────────────────────────

CATEGORIAS = {
    "carnes": ["carne", "pollo", "cerdo", "asado", "bife", "chorizo", "vacío", "nalga"],
    "lacteos": ["leche", "yogur", "queso", "manteca", "crema", "ricota", "caloría"],
    "bebidas": ["gaseosa", "agua", "jugo", "cerveza", "vino", "cola", "fanta", "sprite"],
    "limpieza": ["lavandina", "detergente", "jabón", "suavizante", "quitamanchas", "lavaje"],
    "almacen": ["arroz", "fideos", "harina", "azúcar", "aceite", "sal", "yerba", "café"],
    "panaderia": ["pan", "galletita", "tostada", "facturas", "medialunas"],
    "frutas_verduras": ["fruta", "manzana", "banana", "naranja", "papa", "cebolla", "tomate"],
    "higiene": ["shampoo", "desodorante", "jabón líquido", "cepillo", "pasta dental"],
    "congelados": ["congelado", "medallón", "nugget", "pizza", "helado"],
    "fiambre": ["jamón", "salame", "paleta", "mortadela", "salchicha"],
}


def categorizar(nombre_producto: str) -> str:
    nombre_lower = nombre_producto.lower()
    for categoria, palabras in CATEGORIAS.items():
        if any(p in nombre_lower for p in palabras):
            return categoria
    return "general"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 50)
    log.info(f"SuperAhorro GBA — Scraper iniciando")
    log.info(f"Fecha: {FECHA_HORA}")
    log.info("=" * 50)

    scrapers = [
        ("Carrefour", scrape_carrefour),
        ("Día", scrape_dia),
        ("Coto", scrape_coto),
        ("Changomas", scrape_changomas),
        ("Cencosud", scrape_vea_jumbo_disco),
        ("Maxiconsumo", scrape_maxiconsumo),
        ("Diarco", scrape_diarco),
    ]

    for nombre, fn in scrapers:
        try:
            resultados = fn()
            # Categorizar los que tengan categoría "general"
            for r in resultados:
                if r.get("categoria") == "general" and r.get("producto"):
                    r["categoria"] = categorizar(r["producto"])
            todas_las_ofertas.extend(resultados)
        except Exception as e:
            log.error(f"❌ Error crítico scrapeando {nombre}: {e}")

    # Redes sociales — frágil, no rompe todo si falla
    try:
        social = buscar_redes_sociales()
        todas_las_ofertas.extend(social)
    except Exception as e:
        log.warning(f"⚠️ Búsqueda en redes falló (no crítico): {e}")

    # Deduplicar por (producto, supermercado, precio)
    vistos = set()
    ofertass_unicas = []
    for o in todas_las_ofertas:
        key = (o.get("producto", "")[:50], o.get("supermercado"), o.get("precio"))
        if key not in vistos:
            vistos.add(key)
            ofertass_unicas.append(o)

    # Ordenar por % descuento descendente
    ofertass_unicas.sort(
        key=lambda x: x.get("descuento_pct") or 0,
        reverse=True,
    )

    # Estructura del JSON de salida
    output = {
        "meta": {
            "ultima_actualizacion": FECHA_HORA,
            "fecha": FECHA_HOY,
            "total_ofertas": len(ofertass_unicas),
            "supermercados_scrapeados": list({o["supermercado"] for o in ofertass_unicas}),
        },
        "ofertas": ofertass_unicas,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("=" * 50)
    log.info(f"✅ Scraping terminado: {len(ofertass_unicas)} ofertas únicas")
    log.info(f"📁 Guardado en {OUTPUT_PATH}")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
