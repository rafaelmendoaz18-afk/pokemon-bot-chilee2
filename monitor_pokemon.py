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

# ================= URLS DE LAS TIENDAS =================
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

# Rutas corregidas para Paris
PARIS_URLS = [
    "https://www.paris.cl/juguetes/didacticos-y-recreativos/juegos-de-mesa/?prefn1=brand&prefv1=Pok%C3%A9mon",
    "https://www.paris.cl/juguetes/didacticos-y-recreativos/juegos-de-mesa/?prefn1=brand&prefv1=Pok%C3%A9mon&start=0&sz=40",
    "https://www.paris.cl/listas/cartas-pokemon/",
]

LIDER_URLS = [
    "https://www.lider.cl/catalogo/v/cartas-pokemon?f.seller=Lider",
    "https://www.lider.cl/catalogo/v/precio-cartas-pokemon?f.seller=Lider",
]

# PRODUCTOS DE ALTA DEMANDA PARA VIGILANCIA DIRECTA (incluso si la tienda los oculta del buscador)
PRODUCTOS_VIGILANCIA_DIRECTA = [
    {
        "tienda": "Paris (Directo)",
        "id_unico": "paris_574897999",
        "nombre": "Juego de Cartas Pokémon 30Th Elite Trainer Box English",
        "url": "https://www.paris.cl/juego-de-cartas-pokemon-30th-elite-trainer-box-english-574897999.html",
        "precio": "$79.990"
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

TERMINOS_CARTAS = [
    "carta", "cartas", "tcg", "booster", "blister", "trainer",
    "entrenador", "etb", "sobre", "sobres", "trading", "lata",
    "latas", "tin", "deck", "mazo", "bundle", "partner",
    "collection", "coleccion", "colección", "box", "showcase",
    "toolkit", "binder", "album", "álbum"
]

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

# ================= RIPLEY =================
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

# ================= FALABELLA =================
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

# ================= PARIS =================
def consultar_paris():
    productos = []
    # Soporta enlaces largos (/nombre-574897999.html) y cortos (/574897999.html)
    patron = r'(/(([a-zA-Z0-9\-]+)-)?(\d{9})\.html)'
    vistos_skus = set()

    for url_cat in PARIS_URLS:
        try:
            res = requests.get(url_cat, headers=HEADERS, timeout=20)
            if res.status_code != 200:
                continue

            for link_rel, _, slug, sku in re.findall(patron, res.text):
                if sku in vistos_skus:
                    continue
                vistos_skus.add(sku)

                slug_limpio = urllib.parse.unquote(slug or "")
                if slug_limpio.lower().startswith("mk"):
                    continue

                nombre = slug_limpio.replace("-", " ").title() if slug_limpio else f"Producto Paris {sku}"
                texto = nombre.lower()

                if any(ex in texto for ex in TERMINOS_EXCLUIDOS):
                    continue
                if not slug_limpio or any(tc in texto for tc in TERMINOS_CARTAS) or "pokemon" in texto:
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

# ================= LÍDER =================
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

# ================= VIGILANCIA DIRECTA =================
def consultar_productos_directos():
    """Consulta fichas específicas que se agotan rápido o que la tienda oculta de los buscadores."""
    resultados = []
    for item in PRODUCTOS_VIGILANCIA_DIRECTA:
        try:
            res = requests.get(item["url"], headers=HEADERS, timeout=15)
            if res.status_code == 200:
                html_lower = res.text.lower()
                # Verificar si está agotado
                esta_agotado = any(frase in html_lower for frase in ["agotado", "sin stock", "producto no disponible", "no disponible"])
                disponible = not esta_agotado

                resultados.append({
                    "tienda": item["tienda"],
                    "id_unico": item["id_unico"],
                    "nombre": item["nombre"],
                    "precio": item.get("precio", "Ver precio"),
                    "disponible": disponible,
                    "url": item["url"]
                })
            time.sleep(1)
        except Exception as e:
            print(f"Error en producto directo {item['url']}: {e}")
    return resultados

# ================= CICLO PRINCIPAL =================
def ejecutar_revision():
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"[{ahora}] Escaneando tiendas y lista de vigilancia...")

    prods_ripley = consultar_ripley()
    prods_bigbang = consultar_bigbang()
    prods_falabella = consultar_falabella()
    prods_paris = consultar_paris()
    prods_lider = consultar_lider()
    prods_directos = consultar_productos_directos()

    todos = prods_ripley + prods_bigbang + prods_falabella + prods_paris + prods_lider

    # Sobrescribir con la información más precisa de vigilancia directa
    skus_directos = {p["id_unico"]: p for p in prods_directos}
    for i, p in enumerate(todos):
        if p["id_unico"] in skus_directos:
            todos[i] = skus_directos.pop(p["id_unico"])
    todos.extend(skus_directos.values())

    historial = cargar_historial()
    primera_vez = len(historial) == 0

    nuevos = []
    restocks = []
    skus_activos_ahora = {p["id_unico"] for p in todos if p.get("disponible", True)}

    for p in todos:
        uid = p["id_unico"]

        if uid not in historial:
            nuevos.append(p)
            historial[uid] = {
                "nombre": p["nombre"],
                "precio": p["precio"],
                "disponible": p["disponible"],
                "tienda": p["tienda"],
                "url": p["url"]
            }
        else:
            estaba_disponible = historial[uid].get("disponible", False)
            esta_ahora_disponible = p["disponible"]

            # Si estaba sin stock y ahora está disponible -> ALERTA DE RESTOCK
            if not estaba_disponible and esta_ahora_disponible:
                restocks.append(p)

            historial[uid]["disponible"] = esta_ahora_disponible
            historial[uid]["precio"] = p["precio"]

    # Para tiendas que ocultan productos agotados del buscador
    for uid in list(historial.keys()):
        if uid not in skus_activos_ahora:
            historial[uid]["disponible"] = False

    guardar_historial(historial)

    # 1. Verificación manual (clic en Run workflow)
    if ES_EJECUCION_MANUAL:
        enviar_telegram(
            f"🟢 <b>Monitor Pokémon Activo (Verificación manual)</b>\n\n"
            f"• <b>Ripley:</b> {len(prods_ripley)} artículos\n"
            f"• <b>Big Bang:</b> {len(prods_bigbang)} artículos\n"
            f"• <b>Falabella:</b> {len(prods_falabella)} artículos\n"
            f"• <b>Paris:</b> {len(prods_paris)} artículos (incluye ETB 30th)\n"
            f"• <b>Líder:</b> {len(prods_lider)} artículos\n\n"
            f"• <b>Nuevas publicaciones:</b> {len(nuevos)}\n"
            f"• <b>Restocks detectados:</b> {len(restocks)}\n\n"
            f"Vigilancia directa de stock activa en las 5 tiendas."
        )

    # 2. Mensaje en la primera ejecución
    elif primera_vez:
        enviar_telegram(
            f"✅ <b>Monitor Pokémon Multi-Tienda Actualizado</b>\n\n"
            f"Se cargó el catálogo de las 5 tiendas chilenas.\n"
            f"Incluye vigilancia directa de restock para la ETB 30th Aniversario de Paris."
        )

    # 3. Notificar Restocks
    for p in restocks:
        msg = (
            f"🔄 <b>¡RESTOCK en {escape_html(p['tienda'])}!</b> (Volvió a tener stock)\n\n"
            f"📦 <b>Producto:</b> {escape_html(p['nombre'])}\n"
            f"💰 <b>Precio:</b> {escape_html(p['precio'])}\n"
            f"✅ <b>Estado:</b> ¡Disponible para compra ahora!\n"
            f"🔗 <a href=\"{p['url']}\">Ir a comprar en {escape_html(p['tienda'])}</a>"
        )
        enviar_telegram(msg)
        time.sleep(1)

    # 4. Notificar Productos Nuevos
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
