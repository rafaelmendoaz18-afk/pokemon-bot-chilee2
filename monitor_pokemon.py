import os
import re
import json
import time
import urllib.parse
from datetime import datetime
import requests

# ================= CONFIGURACIÓN =================
TELEGRAM_BOT_TOKEN = "8941547037:AAEBM-NB4ELimXY34liP4fdHn8WmYSUzFl0"
TELEGRAM_CHAT_ID = "1763326840"
INTERVALO_MINUTOS = 5

EN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

# Búsqueda completa: listado de cartas + catálogo de la marca POKÉMON en juguetería
RIPLEY_URLS = [
    "https://simple.ripley.cl/s/list/cartas-pokemon?page=1",
    "https://simple.ripley.cl/s/list/cartas-pokemon?page=2",
    "https://simple.ripley.cl/s/list/cartas-pokemon?page=3",
    "https://simple.ripley.cl/jugueteria-y-ninos/juguetes?page=1&brand=POKEMON",
    "https://simple.ripley.cl/jugueteria-y-ninos/juguetes?page=2&brand=POKEMON",
    "https://simple.ripley.cl/jugueteria-y-ninos/juguetes?page=3&brand=POKEMON",
]

BIGBANG_JSON_URL = "https://bigbang.cl/collections/pokemon-tcg/products.json?limit=250"
BIGBANG_HTML_URL = "https://bigbang.cl/collections/pokemon-tcg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

# Términos completos de TCG / Cartas en inglés y español
TERMINOS_CARTAS = [
    "carta", "cartas", "tcg", "booster", "blister", "trainer",
    "entrenador", "etb", "sobre", "sobres", "trading", "lata",
    "latas", "tin", "deck", "mazo", "bundle", "partner",
    "collection", "coleccion", "colección", "box", "showcase",
    "toolkit", "binder", "album", "álbum"
]

# Exclusiones estrictas para evitar peluches y otros juguetes ajenos
TERMINOS_EXCLUIDOS = [
    "peluche", "peluches", "plush", "mochila", "polera", "poleron",
    "polerón", "pijama", "gorro", "disfraz", "multipack figuras",
    "pistas", "lego", "puzzle", "auto", "figura de accion", "figura accion"
]

def obtener_ruta_historial():
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
    ruta_local = os.path.join(base_dir, "vistos.json")
    try:
        test_file = os.path.join(base_dir, ".test_perm")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return ruta_local
    except Exception:
        return os.path.join(os.path.expanduser("~"), "pokemon_vistos.json")

ARCHIVO_HISTORIAL = obtener_ruta_historial()

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")
        return False

def cargar_vistos():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def guardar_vistos(vistos):
    try:
        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(sorted(list(vistos)), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")

# ================= RIPLEY =================
def consultar_ripley():
    productos = []
    # Captura cualquier URL directa de Ripley terminada en código numérico + 'p'
    patron = r'(/([^\"\'\s<>]+?)-(\d{8,15}[pP]))(?:[\?\"\'&\s>]|$)'
    vistos_skus = set()

    for url_cat in RIPLEY_URLS:
        try:
            res = requests.get(url_cat, headers=HEADERS, timeout=20)
            if res.status_code != 200:
                continue

            for link_rel, slug, sku in re.findall(patron, res.text):
                sku_limpio = sku.lower()
                if sku_limpio in vistos_skus:
                    continue
                vistos_skus.add(sku_limpio)

                # Descodificar caracteres especiales (como %C3%A9 en Pokémon)
                slug_limpio = urllib.parse.unquote(slug)
                nombre = slug_limpio.replace("-", " ").title()
                texto = nombre.lower()

                # 1. Descartar juguetes/peluches
                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                # 2. Confirmar que sea de cartas/TCG
                if any(tc in texto for tc in TERMINOS_CARTAS):
                    productos.append({
                        "tienda": "Ripley (Directo)",
                        "id_unico": f"ripley_{sku_limpio}",
                        "nombre": nombre,
                        "url": f"https://simple.ripley.cl{link_rel}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error en Ripley ({url_cat}): {e}")

    return productos

# ================= BIG BANG COPAG =================
def consultar_bigbang():
    productos = []
    try:
        res = requests.get(BIGBANG_JSON_URL, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            datos = res.json()
            for prod in datos.get("products", []):
                handle = prod.get("handle", "")
                titulo = prod.get("title", "")
                variantes = prod.get("variants", [])
                precio_str = "Consultar"
                if variantes:
                    try:
                        p_num = float(variantes[0].get("price", 0))
                        precio_str = f"${p_num:,.0f}".replace(",", ".")
                    except Exception:
                        pass

                productos.append({
                    "tienda": "Big Bang Copag",
                    "id_unico": f"bigbang_{prod.get('id', handle)}",
                    "nombre": titulo,
                    "precio": precio_str,
                    "url": f"https://bigbang.cl/products/{handle}"
                })
            if productos:
                return productos
    except Exception:
        pass

    try:
        res = requests.get(BIGBANG_HTML_URL, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            patron_bb = r'href=[\"\'](?:/collections/[^/]+)?(/products/([a-zA-Z0-9\-]+))(?:\?[^\"\']*)?[\"\']'
            vistos_bb = set()
            for full_link, slug in re.findall(patron_bb, res.text):
                if slug in vistos_bb:
                    continue
                vistos_bb.add(slug)
                productos.append({
                    "tienda": "Big Bang Copag",
                    "id_unico": f"bigbang_{slug}",
                    "nombre": slug.replace("-", " ").title(),
                    "precio": "Ver en tienda",
                    "url": f"https://bigbang.cl/products/{slug}"
                })
    except Exception as e:
        print(f"Error en Big Bang: {e}")

    return productos

# ================= CICLO DE REVISIÓN =================
def ejecutar_revision():
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"[{ahora}] Escaneando tiendas...")

    prods_ripley = consultar_ripley()
    print(f"[{ahora}] Ripley directo: {len(prods_ripley)} artículos TCG encontrados.")

    prods_bigbang = consultar_bigbang()
    print(f"[{ahora}] Big Bang Copag: {len(prods_bigbang)} artículos TCG encontrados.")

    todos = prods_ripley + prods_bigbang

    vistos = cargar_vistos()
    primera_vez = len(vistos) == 0
    nuevos = []

    for p in todos:
        uid = p["id_unico"]
        if uid not in vistos:
            vistos.add(uid)
            nuevos.append(p)

    guardar_vistos(vistos)

    if primera_vez:
        print(f"Registro inicial con {len(vistos)} productos.")
        enviar_telegram(
            f"✅ *Monitor Pokémon Actualizado*\n\n"
            f"• *Ripley directo:* {len(prods_ripley)} artículos TCG encontrados.\n"
            f"• *Big Bang Copag:* {len(prods_bigbang)} artículos TCG encontrados.\n\n"
            f"Catálogo completo cargado. Recibirás alerta de cualquier publicación nueva."
        )
        return

    for p in nuevos:
        precio_texto = f"\n💰 *Precio:* {p['precio']}" if "precio" in p else ""
        mensaje = (
            f"🚨 *¡Nuevo producto en {p['tienda']}!*\n\n"
            f"📦 *Producto:* {p['nombre']}"
            f"{precio_texto}\n"
            f"🔗 *Enlace:* [Ver producto]({p['url']})"
        )
        enviar_telegram(mensaje)
        time.sleep(1)

if __name__ == "__main__":
    if EN_GITHUB_ACTIONS:
        ejecutar_revision()
    else:
        try:
            while True:
                ejecutar_revision()
                print(f"Esperando {INTERVALO_MINUTOS} minutos...\n")
                time.sleep(INTERVALO_MINUTOS * 60)
        except KeyboardInterrupt:
            print("Detenido.")
