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
ES_EJECUCION_MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
ARCHIVO_HISTORIAL = "vistos.json"

# ================= URLS DE LAS 5 TIENDAS =================
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

FALABELLA_URLS = [
    "https://www.falabella.com/falabella-cl/search?Ntt=cartas+pokemon&f.DerivedProduct.pt_seller=FALABELLA",
    "https://www.falabella.com/falabella-cl/search?Ntt=pokemon+tcg&f.DerivedProduct.pt_seller=FALABELLA",
]

PARIS_URLS = [
    "https://www.paris.cl/jugueteria/juegos-de-mesa/cartas-coleccionables/?prefn1=brand&prefv1=Pok%C3%A9mon",
    "https://www.paris.cl/search?q=cartas+pokemon",
]

LIDER_URLS = [
    "https://www.lider.cl/catalogo/v/cartas-pokemon?f.seller=Lider",
    "https://www.lider.cl/catalogo/v/precio-cartas-pokemon?f.seller=Lider",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

# Términos de cartas coleccionables
TERMINOS_CARTAS = [
    "carta", "cartas", "tcg", "booster", "blister", "trainer",
    "entrenador", "etb", "sobre", "sobres", "trading", "lata",
    "latas", "tin", "deck", "mazo", "bundle", "partner",
    "collection", "coleccion", "colección", "box", "showcase",
    "toolkit", "binder", "album", "álbum"
]

# Exclusiones de peluches y juguetes ajenos
TERMINOS_EXCLUIDOS = [
    "peluche", "peluches", "plush", "mochila", "polera", "poleron",
    "polerón", "pijama", "gorro", "disfraz", "multipack figuras",
    "pistas", "lego", "puzzle", "auto", "figura de accion", "figura accion"
]

def escape_html(texto):
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"Error Telegram: {r.status_code} - {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")
        return False

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                elif isinstance(data, list):
                    return {k: {"disponible": True} for k in data}
        except Exception as e:
            print(f"Aviso cargando historial: {e}")
    return {}

def guardar_historial(estado):
    try:
        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")

# ================= 1. RIPLEY =================
def consultar_ripley():
    productos = []
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

                slug_limpio = urllib.parse.unquote(slug)
                nombre = slug_limpio.replace("-", " ").title()
                texto = nombre.lower()

                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                if any(tc in texto for tc in TERMINOS_CARTAS):
                    productos.append({
                        "tienda": "Ripley (Directo)",
                        "id_unico": f"ripley_{sku_limpio}",
                        "nombre": nombre,
                        "precio": "Ver en Ripley",
                        "disponible": True,
                        "url": f"https://simple.ripley.cl{link_rel}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error en Ripley ({url_cat}): {e}")

    return productos

# ================= 2. BIG BANG COPAG =================
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
                
                disponible = any(v.get("available", False) for v in variantes)
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
                    "disponible": disponible,
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
                    "disponible": True,
                    "url": f"https://bigbang.cl/products/{slug}"
                })
    except Exception as e:
        print(f"Error en Big Bang: {e}")

    return productos

# ================= 3. FALABELLA =================
def consultar_falabella():
    productos = []
    patron = r'(/falabella-cl/product/(\d+)/([^/\"\'\?]+)/(\d+))'
    vistos_skus = set()

    for url_cat in FALABELLA_URLS:
        try:
            res = requests.get(url_cat, headers=HEADERS, timeout=20)
            if res.status_code != 200:
                continue

            for link_rel, sku1, slug, sku2 in re.findall(patron, res.text):
                sku = sku1 or sku2
                if sku in vistos_skus:
                    continue
                vistos_skus.add(sku)

                slug_limpio = urllib.parse.unquote(slug)
                nombre = slug_limpio.replace("-", " ").title()
                texto = nombre.lower()

                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                if any(tc in texto for tc in TERMINOS_CARTAS) or "pokemon" in texto:
                    productos.append({
                        "tienda": "Falabella (Directo)",
                        "id_unico": f"falabella_{sku}",
                        "nombre": nombre,
                        "precio": "Ver en Falabella",
                        "disponible": True,
                        "url": f"https://www.falabella.com{link_rel}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error en Falabella ({url_cat}): {e}")

    return productos

# ================= 4. PARIS =================
def consultar_paris():
    productos = []
    # SKUs directos de Paris: 9 dígitos numéricos terminados en .html (sin códigos MK/MP)
    patron = r'(/([a-zA-Z0-9\-]+)-(\d{9})\.html)'
    vistos_skus = set()

    for url_cat in PARIS_URLS:
        try:
            res = requests.get(url_cat, headers=HEADERS, timeout=20)
            if res.status_code != 200:
                continue

            for link_rel, slug, sku in re.findall(patron, res.text):
                if sku in vistos_skus:
                    continue
                vistos_skus.add(sku)

                slug_limpio = urllib.parse.unquote(slug)
                nombre = slug_limpio.replace("-", " ").title()
                texto = nombre.lower()

                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                if any(tc in texto for tc in TERMINOS_CARTAS):
                    productos.append({
                        "tienda": "Paris (Directo)",
                        "id_unico": f"paris_{sku}",
                        "nombre": nombre,
                        "precio": "Ver en Paris",
                        "disponible": True,
                        "url": f"https://www.paris.cl{link_rel}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error en Paris ({url_cat}): {e}")

    return productos

# ================= 5. LÍDER =================
def consultar_lider():
    productos = []
    patron = r'(/catalogo/product/sku/(\d+)/([^/\"\'\?]+)|/product/sku/(\d+)/([^/\"\'\?]+))'
    vistos_skus = set()

    for url_cat in LIDER_URLS:
        try:
            res = requests.get(url_cat, headers=HEADERS, timeout=20)
            if res.status_code != 200:
                continue

            for link_match, sku1, slug1, sku2, slug2 in re.findall(patron, res.text):
                sku = sku1 or sku2
                slug = slug1 or slug2
                if sku in vistos_skus:
                    continue
                vistos_skus.add(sku)

                slug_limpio = urllib.parse.unquote(slug)
                nombre = slug_limpio.replace("-", " ").title()
                texto = nombre.lower()

                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                if any(tc in texto for tc in TERMINOS_CARTAS):
                    productos.append({
                        "tienda": "Líder (Directo)",
                        "id_unico": f"lider_{sku}",
                        "nombre": nombre,
                        "precio": "Ver en Líder",
                        "disponible": True,
                        "url": f"https://www.lider.cl{link_match}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error en Líder ({url_cat}): {e}")

    return productos

# ================= REVISIÓN Y DETECCIÓN =================
def ejecutar_revision():
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"[{ahora}] Escaneando las 5 tiendas chilenas...")

    prods_ripley = consultar_ripley()
    print(f"[{ahora}] Ripley directo: {len(prods_ripley)} artículos TCG.")

    prods_bigbang = consultar_bigbang()
    bb_disp = sum(1 for p in prods_bigbang if p["disponible"])
    bb_agotados = len(prods_bigbang) - bb_disp
    print(f"[{ahora}] Big Bang Copag: {len(prods_bigbang)} artículos ({bb_disp} en stock, {bb_agotados} agotados).")

    prods_falabella = consultar_falabella()
    print(f"[{ahora}] Falabella directo: {len(prods_falabella)} artículos TCG.")

    prods_paris = consultar_paris()
    print(f"[{ahora}] Paris directo: {len(prods_paris)} artículos TCG.")

    prods_lider = consultar_lider()
    print(f"[{ahora}] Líder directo: {len(prods_lider)} artículos TCG.")

    todos = prods_ripley + prods_bigbang + prods_falabella + prods_paris + prods_lider

    historial = cargar_historial()
    primera_vez = len(historial) == 0

    nuevos = []
    restocks = []
    skus_activos_ahora = {p["id_unico"] for p in todos}

    for p in todos:
        uid = p["id_unico"]

        if uid not in historial:
            # Producto totalmente nuevo
            nuevos.append(p)
            historial[uid] = {
                "nombre": p["nombre"],
                "precio": p["precio"],
                "disponible": p["disponible"],
                "tienda": p["tienda"],
                "url": p["url"]
            }
        else:
            # Producto ya conocido: verificar si volvió a tener stock (Restock)
            estaba_disponible = historial[uid].get("disponible", False)
            esta_ahora_disponible = p["disponible"]

            if not estaba_disponible and esta_ahora_disponible:
                restocks.append(p)

            historial[uid]["disponible"] = esta_ahora_disponible
            historial[uid]["precio"] = p["precio"]

    # Marcar como sin stock si desapareció del catálogo de retail
    for uid in list(historial.keys()):
        if not uid.startswith("bigbang_") and uid not in skus_activos_ahora:
            historial[uid]["disponible"] = False

    guardar_historial(historial)

    # 1. Alerta de Verificación Manual (al presionar Run workflow)
    if ES_EJECUCION_MANUAL:
        enviar_telegram(
            f"🟢 <b>Monitor Pokémon Activo (Verificación manual)</b>\n\n"
            f"• <b>Ripley directo:</b> {len(prods_ripley)} artículos\n"
            f"• <b>Big Bang:</b> {len(prods_bigbang)} artículos ({bb_disp} en stock, {bb_agotados} agotados)\n"
            f"• <b>Falabella directo:</b> {len(prods_falabella)} artículos\n"
            f"• <b>Paris directo:</b> {len(prods_paris)} artículos\n"
            f"• <b>Líder directo:</b> {len(prods_lider)} artículos\n\n"
            f"• <b>Novedades en este escaneo:</b> {len(nuevos)}\n"
            f"• <b>Restocks detectados:</b> {len(restocks)}\n\n"
            f"Vigilando 24/7 en la nube las 5 tiendas."
        )

    # 2. Mensaje en la primera ejecución
    elif primera_vez:
        enviar_telegram(
            f"✅ <b>Monitor Pokémon Multi-Tienda Activado</b>\n\n"
            f"Vigilando solo productos directos (sin Marketplace):\n"
            f"• Ripley: {len(prods_ripley)}\n"
            f"• Big Bang Copag: {len(prods_bigbang)}\n"
            f"• Falabella: {len(prods_falabella)}\n"
            f"• Paris: {len(prods_paris)}\n"
            f"• Líder: {len(prods_lider)}\n\n"
            f"Te avisaré ante cualquier publicación nueva o reposición de stock (Restock)."
        )

    # 3. Notificar Restocks (Volvieron a tener stock)
    for p in restocks:
        msg = (
            f"🔄 <b>¡RESTOCK en {escape_html(p['tienda'])}!</b> (Volvió a tener stock)\n\n"
            f"📦 <b>Producto:</b> {escape_html(p['nombre'])}\n"
            f"💰 <b>Precio:</b> {escape_html(p['precio'])}\n"
            f"✅ <b>Estado:</b> ¡Disponible para compra ahora!\n"
            f"🔗 <a href=\"{p['url']}\">Ir a comprar</a>"
        )
        enviar_telegram(msg)
        time.sleep(1)

    # 4. Notificar Productos Nuevos publicados
    for p in nuevos:
        estado_disp = "✅ Con stock" if p["disponible"] else "⚠️ Sin stock / Preventa"
        msg = (
            f"🚨 <b>¡Nuevo producto en {escape_html(p['tienda'])}!</b>\n\n"
            f"📦 <b>Producto:</b> {escape_html(p['nombre'])}\n"
            f"💰 <b>Precio:</b> {escape_html(p['precio'])}\n"
            f"📌 <b>Estado:</b> {estado_disp}\n"
            f"🔗 <a href=\"{p['url']}\">Ver en la tienda</a>"
        )
        enviar_telegram(msg)
        time.sleep(1)

# ================= EJECUCIÓN DEL SCRIPT =================
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
