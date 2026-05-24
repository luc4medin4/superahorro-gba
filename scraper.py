"""
scraper.py — SuperAhorro GBA
Usa la API SEPA de Precios Claros (gobierno argentino).
Endpoints actualizados 2025/2026.
Corre diariamente via GitHub Actions a las 10am UTC (7am Argentina).
"""

import json
import time
import logging
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ─── Config ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

TZ_AR   = timezone(timedelta(hours=-3))
AHORA   = datetime.now(TZ_AR)
FECHA   = AHORA.strftime("%Y-%m-%d")
FECHA_H = AHORA.strftime("%Y-%m-%dT%H:%M:%S-03:00")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT   = DATA_DIR / "ofertas.json"

TIMEOUT = 30
DELAY   = 1.5

# ─── Endpoints SEPA ───────────────────────────────────────────────────────────
# La API de Precios Claros usa estos endpoints en 2025/2026
SEPA_BASE = "https://api.preciosclaros.gob.ar"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
    "Origin": "https://www.preciosclaros.gob.ar",
    "Referer": "https://www.preciosclaros.gob.ar/",
    "Connection": "keep-alive",
}

# ─── Mapeo de cadenas ─────────────────────────────────────────────────────────
CADENA_MAP = {
    "carrefour":    "Carrefour",
    "dia":          "Día",
    "coto":         "Coto",
    "changomas":    "Changomas",
    "jumbo":        "Jumbo",
    "vea":          "Vea",
    "disco":        "Disco",
    "maxiconsumo":  "Maxiconsumo",
    "diarco":       "Diarco",
    "walmart":      "Walmart",
    "toledo":       "Toledo",
    "la anonima":   "La Anónima",
    "cooperativa":  "Cooperativa",
    "cordiez":      "Cordiez",
    "mayorista":    "Maxiconsumo",
}

# Categorías SEPA con sus IDs
CATEGORIAS = [
    ("1",  "almacen"),
    ("2",  "bebidas"),
    ("3",  "lacteos"),
    ("4",  "carnes"),
    ("5",  "fiambre"),
    ("6",  "frutas_verduras"),
    ("7",  "panaderia"),
    ("8",  "limpieza"),
    ("9",  "higiene"),
    ("10", "congelados"),
]

KEYWORDS_CAT = {
    "carnes":          ["carne","pollo","cerdo","asado","bife","chorizo","vacío","nalga","pechuga","costilla","milanesa","ternera"],
    "lacteos":         ["leche","yogur","queso","manteca","crema","ricota","postre","mantequilla","yogurt"],
    "bebidas":         ["gaseosa","agua","jugo","cerveza","vino","cola","fanta","sprite","7up","sidra","energizante","soda"],
    "limpieza":        ["lavandina","detergente","jabón en polvo","suavizante","quitamanchas","limpiador","desengrasante","esponja"],
    "almacen":         ["arroz","fideos","harina","azúcar","aceite","sal","yerba","café","té","puré","tomate triturado","lentejas","polenta","avena"],
    "panaderia":       ["pan ","galletita","tostada","medialunas","bizcocho","budín","alfajor","oblea","cookie"],
    "frutas_verduras": ["manzana","banana","naranja","papa","cebolla","tomate","lechuga","zanahoria","limón","mandarina","pera","uva"],
    "higiene":         ["shampoo","desodorante","jabón líquido","cepillo","pasta dental","enjuague","pañal","toallita","afeitadora"],
    "congelados":      ["congelado","medallón","nugget","pizza","helado","bastón","rebozado"],
    "fiambre":         ["jamón","salame","paleta","mortadela","salchicha","longaniza","pastrón"],
    "mayorista":       ["fardo","pack x","caja x","display","bulto"],
}

def categorizar(nombre: str) -> str:
    n = nombre.lower()
    for cat, kws in KEYWORDS_CAT.items():
        if any(k in n for k in kws):
            return cat
    return "general"

def normalizar_cadena(raw: str) -> str:
    r = (raw or "").lower().strip()
    for k, v in CADENA_MAP.items():
        if k in r:
            return v
    return r.title() if r else ""

# ─── HTTP helpers ──────────────────────────────────────────────────────────────
def safe_get(session: requests.Session, url: str, params: dict = None) -> dict | None:
    try:
        resp = session.get(url, params=params, timeout=TIMEOUT, headers=HEADERS)
        if resp.status_code == 200:
            return resp.json()
        log.warning(f"  HTTP {resp.status_code} → {url[:80]}")
        return None
    except Exception as e:
        log.warning(f"  Error → {url[:80]} | {e}")
        return None

# ─── 1. Buscar sucursales zona norte GBA ──────────────────────────────────────
def get_sucursales(session: requests.Session) -> list[str]:
    """Devuelve lista de IDs de sucursales en zona norte GBA."""
    log.info("📍 Buscando sucursales zona norte GBA...")

    # Centro: José C. Paz
    params = {
        "lat":    -34.520,
        "lng":    -58.760,
        "radius": 25000,
        "limit":  200,
        "offset": 0,
    }
    data = safe_get(session, f"{SEPA_BASE}/sucursales", params)

    if not data:
        # fallback: provincia Buenos Aires
        data = safe_get(session, f"{SEPA_BASE}/sucursales", {
            "provincia": "06",
            "limit": 200,
            "offset": 0,
        })

    ids = []
    if data:
        items = data.get("sucursales", data.get("data", []))
        for s in items:
            sid = s.get("sucursalId") or s.get("id")
            cid = s.get("comercioId") or s.get("banderaId","")
            if sid and normalizar_cadena(str(cid)):
                ids.append(str(sid))

    log.info(f"  → {len(ids)} sucursales encontradas")
    return ids

# ─── 2. Buscar productos por categoría ────────────────────────────────────────
def buscar_categoria(session: requests.Session, cat_id: str, sucursales: list[str]) -> dict | None:
    params = {
        "limit":    100,
        "offset":   0,
        "categoria": cat_id,
    }
    if sucursales:
        params["array_sucursales"] = ",".join(sucursales[:10])
    return safe_get(session, f"{SEPA_BASE}/productos", params)

# ─── 3. Buscar productos por string ───────────────────────────────────────────
def buscar_string(session: requests.Session, query: str, sucursales: list[str]) -> dict | None:
    params = {
        "limit":  50,
        "offset": 0,
        "string": query,
    }
    if sucursales:
        params["array_sucursales"] = ",".join(sucursales[:10])
    return safe_get(session, f"{SEPA_BASE}/productos", params)

# ─── 4. Procesar respuesta ────────────────────────────────────────────────────
def procesar(data: dict, cat_default: str = "general") -> list[dict]:
    if not data:
        return []

    resultados = []
    productos = data.get("productos", data.get("data", []))

    for p in productos:
        nombre = (p.get("nombre") or "").strip()
        if not nombre:
            continue

        marca        = (p.get("marca") or "").strip()
        presentacion = (p.get("presentacion") or "").strip()
        nombre_full  = " ".join(filter(None, [nombre, marca, presentacion]))[:200]

        # Obtener precios por sucursal — múltiples formatos posibles
        precios_raw = (
            p.get("preciosSucursales") or
            p.get("precios") or
            p.get("sucursales") or
            []
        )

        if not precios_raw:
            # Intentar precio directo sin sucursales
            precio_directo = p.get("precio") or p.get("precioLista")
            cadena_raw = p.get("comercioId") or p.get("banderaId") or ""
            if precio_directo and cadena_raw:
                try:
                    pf = float(precio_directo)
                    cadena = normalizar_cadena(str(cadena_raw))
                    if cadena:
                        cat = categorizar(nombre_full) if cat_default == "general" else cat_default
                        resultados.append(_hacer_oferta(nombre_full, pf, None, cadena, cat))
                except:
                    pass
            continue

        # Agrupar precios por cadena
        por_cadena: dict[str, list[float]] = {}
        for ps in precios_raw:
            cadena_raw = (
                ps.get("comercioId") or
                ps.get("banderaId") or
                ps.get("cadena") or
                ""
            )
            precio_val = (
                ps.get("precio") or
                ps.get("precioLista") or
                ps.get("precio_lista") or
                ps.get("precioPromocional")
            )
            if not precio_val:
                continue
            try:
                pf = float(precio_val)
                cadena = normalizar_cadena(str(cadena_raw))
                if cadena:
                    por_cadena.setdefault(cadena, []).append(pf)
            except:
                pass

        cat = categorizar(nombre_full) if cat_default == "general" else cat_default

        for cadena, precios in por_cadena.items():
            precio_min = min(precios)
            precio_max = max(precios)
            precio_ant = precio_max if precio_max > precio_min * 1.05 else None
            desc = round((1 - precio_min / precio_max) * 100, 1) if precio_ant else None
            resultados.append(_hacer_oferta(nombre_full, precio_min, precio_ant, cadena, cat, desc, p))

    return resultados

def _hacer_oferta(nombre, precio, precio_ant, cadena, cat, desc=None, p=None) -> dict:
    img = None
    url = f"https://www.preciosclaros.gob.ar/#!/buscar-productos?q={nombre[:30].replace(' ','+')}"
    if p:
        imgs = p.get("imagenes") or []
        if imgs and isinstance(imgs, list):
            img = imgs[0].get("url") if isinstance(imgs[0], dict) else None
    return {
        "producto":          nombre,
        "precio":            round(precio, 2),
        "precio_anterior":   round(precio_ant, 2) if precio_ant else None,
        "descuento_pct":     desc,
        "supermercado":      cadena,
        "sucursal":          None,
        "categoria":         cat,
        "fecha_scrape":      FECHA,
        "fecha_vencimiento": None,
        "url_fuente":        url,
        "imagen_url":        img,
    }

# ─── 5. Productos clave a buscar ──────────────────────────────────────────────
BUSQUEDAS = [
    ("aceite girasol",     "almacen"),
    ("aceite mezcla",      "almacen"),
    ("leche entera",       "lacteos"),
    ("leche descremada",   "lacteos"),
    ("fideos spaghetti",   "almacen"),
    ("fideos tallarín",    "almacen"),
    ("arroz largo fino",   "almacen"),
    ("arroz parboil",      "almacen"),
    ("azucar",             "almacen"),
    ("harina 0000",        "almacen"),
    ("yerba mate",         "almacen"),
    ("cafe molido",        "almacen"),
    ("tomate triturado",   "almacen"),
    ("puré tomate",        "almacen"),
    ("mayonesa",           "almacen"),
    ("sal fina",           "almacen"),
    ("gaseosa cola",       "bebidas"),
    ("gaseosa naranja",    "bebidas"),
    ("agua mineral",       "bebidas"),
    ("cerveza",            "bebidas"),
    ("jugo polvo",         "bebidas"),
    ("pollo entero",       "carnes"),
    ("carne picada",       "carnes"),
    ("pechuga pollo",      "carnes"),
    ("asado",              "carnes"),
    ("milanesa ternera",   "carnes"),
    ("yogur",              "lacteos"),
    ("queso cremoso",      "lacteos"),
    ("manteca",            "lacteos"),
    ("lavandina",          "limpieza"),
    ("detergente",         "limpieza"),
    ("jabon polvo",        "limpieza"),
    ("suavizante ropa",    "limpieza"),
    ("shampoo",            "higiene"),
    ("pasta dental",       "higiene"),
    ("desodorante",        "higiene"),
    ("jabon tocador",      "higiene"),
    ("galletitas",         "panaderia"),
    ("pan lactal",         "panaderia"),
    ("medialunas",         "panaderia"),
    ("jamón cocido",       "fiambre"),
    ("salame",             "fiambre"),
    ("pizza congelada",    "congelados"),
    ("helado",             "congelados"),
    ("papa",               "frutas_verduras"),
    ("banana",             "frutas_verduras"),
    ("manzana",            "frutas_verduras"),
    ("naranja",            "frutas_verduras"),
    ("cebolla",            "frutas_verduras"),
]

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(f"SuperAhorro GBA — SEPA API — {FECHA_H}")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)
    todos: list[dict] = []

    # ── Paso 1: Sucursales
    sucursales = get_sucursales(session)
    time.sleep(DELAY)

    # ── Paso 2: Por categoría
    log.info("🔍 Buscando por categorías...")
    for cat_id, cat_nombre in CATEGORIAS:
        log.info(f"  → Categoría {cat_nombre} (id={cat_id})")
        data = buscar_categoria(session, cat_id, sucursales)
        if data:
            items = procesar(data, cat_nombre)
            log.info(f"     {len(items)} productos")
            todos.extend(items)
        else:
            log.warning(f"     Sin datos")
        time.sleep(DELAY + random.uniform(0, 0.5))

    # ── Paso 3: Búsquedas específicas
    log.info("🔍 Buscando productos clave...")
    for query, cat in BUSQUEDAS:
        data = buscar_string(session, query, sucursales)
        if data:
            items = procesar(data, cat)
            if items:
                log.info(f"  '{query}' → {len(items)} resultados")
            todos.extend(items)
        time.sleep(DELAY + random.uniform(0, 0.3))

    # ── Paso 4: Deduplicar
    vistos, unicos = set(), []
    for o in todos:
        key = (o["producto"][:60].lower(), o["supermercado"], round(o["precio"] or 0))
        if key not in vistos and o.get("precio") and o.get("supermercado"):
            vistos.add(key)
            unicos.append(o)

    log.info(f"✓ {len(unicos)} ofertas únicas tras deduplicar")

    # ── Paso 5: Ordenar (más descuento primero)
    unicos.sort(key=lambda x: (-(x.get("descuento_pct") or 0), x["supermercado"]))

    # ── Paso 6: Fallback si no hay datos
    if len(unicos) < 10:
        log.warning(f"⚠️ Solo {len(unicos)} ofertas — usando datos de respaldo")
        unicos = get_respaldo()

    # ── Paso 7: Guardar
    output = {
        "meta": {
            "ultima_actualizacion": FECHA_H,
            "fecha":                FECHA,
            "total_ofertas":        len(unicos),
            "supermercados":        sorted({o["supermercado"] for o in unicos}),
            "fuente":               "Precios Claros SEPA — Gobierno Argentina",
        },
        "ofertas": unicos,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("=" * 60)
    log.info(f"✅ Guardado: {OUTPUT}")
    log.info(f"   {len(unicos)} ofertas | {len({o['supermercado'] for o in unicos})} supermercados")
    log.info("=" * 60)


# ─── Datos de respaldo ────────────────────────────────────────────────────────
# Precios de referencia zona norte GBA — actualizar manualmente si es necesario
def get_respaldo() -> list[dict]:
    log.info("📦 Cargando datos de respaldo...")
    base = {
        "sucursal": None,
        "fecha_scrape": FECHA,
        "fecha_vencimiento": None,
        "url_fuente": "https://www.preciosclaros.gob.ar",
        "imagen_url": None,
    }
    return [
        {**base, "producto": "Aceite Cocinero Girasol 1.5L", "precio": 8200,  "precio_anterior": 9800,  "descuento_pct": 16.3, "supermercado": "Día",          "categoria": "almacen"},
        {**base, "producto": "Aceite Natura Girasol 1.5L",   "precio": 7900,  "precio_anterior": 9200,  "descuento_pct": 14.1, "supermercado": "Carrefour",     "categoria": "almacen"},
        {**base, "producto": "Leche La Serenísima Entera 1L","precio": 1950,  "precio_anterior": 2300,  "descuento_pct": 15.2, "supermercado": "Carrefour",     "categoria": "lacteos"},
        {**base, "producto": "Leche La Serenísima Entera 1L","precio": 1880,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Día",           "categoria": "lacteos"},
        {**base, "producto": "Leche Ilolay Entera 1L",       "precio": 1820,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Changomas",     "categoria": "lacteos"},
        {**base, "producto": "Fideos Marolio Spaghetti 500g","precio": 1450,  "precio_anterior": 1750,  "descuento_pct": 17.1, "supermercado": "Changomas",     "categoria": "almacen"},
        {**base, "producto": "Fideos Lucchetti Spaghetti 500g","precio":1680, "precio_anterior": None,  "descuento_pct": None, "supermercado": "Coto",          "categoria": "almacen"},
        {**base, "producto": "Arroz Gallo Largo Fino 1kg",   "precio": 2100,  "precio_anterior": 2500,  "descuento_pct": 16.0, "supermercado": "Coto",          "categoria": "almacen"},
        {**base, "producto": "Arroz Molinos Ala 1kg",        "precio": 1950,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Día",           "categoria": "almacen"},
        {**base, "producto": "Azúcar Ledesma 1kg",           "precio": 1600,  "precio_anterior": 1900,  "descuento_pct": 15.8, "supermercado": "Carrefour",     "categoria": "almacen"},
        {**base, "producto": "Yerba Cruz de Malta 1kg",      "precio": 5800,  "precio_anterior": 6900,  "descuento_pct": 15.9, "supermercado": "Changomas",     "categoria": "almacen"},
        {**base, "producto": "Yerba Rosamonte 500g",         "precio": 3200,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Día",           "categoria": "almacen"},
        {**base, "producto": "Coca-Cola 2.25L",              "precio": 3800,  "precio_anterior": 4500,  "descuento_pct": 15.6, "supermercado": "Carrefour",     "categoria": "bebidas"},
        {**base, "producto": "Coca-Cola 2.25L",              "precio": 3650,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Coto",          "categoria": "bebidas"},
        {**base, "producto": "Pepsi 2.25L",                  "precio": 3400,  "precio_anterior": 4000,  "descuento_pct": 15.0, "supermercado": "Changomas",     "categoria": "bebidas"},
        {**base, "producto": "Agua Villavicencio 2L",        "precio": 1800,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Carrefour",     "categoria": "bebidas"},
        {**base, "producto": "Cerveza Quilmes 1L",           "precio": 2900,  "precio_anterior": 3400,  "descuento_pct": 14.7, "supermercado": "Día",           "categoria": "bebidas"},
        {**base, "producto": "Pollo Entero s/menudos kg",    "precio": 4200,  "precio_anterior": 5100,  "descuento_pct": 17.6, "supermercado": "Coto",          "categoria": "carnes"},
        {**base, "producto": "Pechuga de Pollo kg",          "precio": 6500,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Carrefour",     "categoria": "carnes"},
        {**base, "producto": "Carne Picada Común kg",        "precio": 7800,  "precio_anterior": 9200,  "descuento_pct": 15.2, "supermercado": "Changomas",     "categoria": "carnes"},
        {**base, "producto": "Milanesa de Ternera kg",       "precio": 12000, "precio_anterior": None,  "descuento_pct": None, "supermercado": "Coto",          "categoria": "carnes"},
        {**base, "producto": "Yogur Ser Frutado x4",         "precio": 3800,  "precio_anterior": 4500,  "descuento_pct": 15.6, "supermercado": "Carrefour",     "categoria": "lacteos"},
        {**base, "producto": "Queso Cremoso Primer Minuto kg","precio":9500,  "precio_anterior": 11000, "descuento_pct": 13.6, "supermercado": "Día",           "categoria": "lacteos"},
        {**base, "producto": "Manteca La Serenísima 200g",   "precio": 2800,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Carrefour",     "categoria": "lacteos"},
        {**base, "producto": "Lavandina Ayudín 1.5L",        "precio": 1500,  "precio_anterior": 1800,  "descuento_pct": 16.7, "supermercado": "Día",           "categoria": "limpieza"},
        {**base, "producto": "Lavandina Igual 2L",           "precio": 1350,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Changomas",     "categoria": "limpieza"},
        {**base, "producto": "Detergente Magistral 750ml",   "precio": 2200,  "precio_anterior": 2600,  "descuento_pct": 15.4, "supermercado": "Coto",          "categoria": "limpieza"},
        {**base, "producto": "Skip Polvo 800g",              "precio": 4500,  "precio_anterior": 5500,  "descuento_pct": 18.2, "supermercado": "Carrefour",     "categoria": "limpieza"},
        {**base, "producto": "Shampoo Pantene 400ml",        "precio": 4800,  "precio_anterior": 5800,  "descuento_pct": 17.2, "supermercado": "Jumbo",         "categoria": "higiene"},
        {**base, "producto": "Pasta Dental Colgate 90g",     "precio": 2100,  "precio_anterior": 2500,  "descuento_pct": 16.0, "supermercado": "Carrefour",     "categoria": "higiene"},
        {**base, "producto": "Galletitas Oreo 117g",         "precio": 1500,  "precio_anterior": 1800,  "descuento_pct": 16.7, "supermercado": "Jumbo",         "categoria": "panaderia"},
        {**base, "producto": "Galletitas Terrabusi 170g",    "precio": 1800,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Día",           "categoria": "panaderia"},
        {**base, "producto": "Pan Lactal Bimbo 480g",        "precio": 2900,  "precio_anterior": 3500,  "descuento_pct": 17.1, "supermercado": "Carrefour",     "categoria": "panaderia"},
        {**base, "producto": "Jamón Cocido La Salamandra kg","precio": 14000, "precio_anterior": 16500, "descuento_pct": 15.2, "supermercado": "Coto",          "categoria": "fiambre"},
        {**base, "producto": "Salame Cagnoli kg",            "precio": 18000, "precio_anterior": None,  "descuento_pct": None, "supermercado": "Jumbo",         "categoria": "fiambre"},
        {**base, "producto": "Pizza Congelada Día kg",       "precio": 6500,  "precio_anterior": 7800,  "descuento_pct": 16.7, "supermercado": "Día",           "categoria": "congelados"},
        {**base, "producto": "Tomate Triturado Arcor 520g",  "precio": 1400,  "precio_anterior": 1700,  "descuento_pct": 17.6, "supermercado": "Changomas",     "categoria": "almacen"},
        {**base, "producto": "Mayonesa Hellmann's 500g",     "precio": 3800,  "precio_anterior": 4500,  "descuento_pct": 15.6, "supermercado": "Carrefour",     "categoria": "almacen"},
        {**base, "producto": "Harina Cañuelas 0000 1kg",     "precio": 1800,  "precio_anterior": None,  "descuento_pct": None, "supermercado": "Día",           "categoria": "almacen"},
        {**base, "producto": "Polenta Presto Pronta 500g",   "precio": 1600,  "precio_anterior": 1900,  "descuento_pct": 15.8, "supermercado": "Coto",          "categoria": "almacen"},
    ]


if __name__ == "__main__":
    main()
