#!/usr/bin/env python3
"""Genera las páginas de catálogo a partir de la planilla ORIGINAL de costos.

Fuente de datos
---------------
* Categorías Apple/Samsung/DJI/Sonos/Otros: planilla de costos (privada). De cada
  fila se toma solamente el código, la descripción y el PRECIO DE VENTA. Las
  columnas MAYORISTA, Unit Cost, Profit y las de cada proveedor no salen de acá:
  no viajan al HTML ni existen en la página publicada.
* Windows: no está en la planilla de costos, así que se sigue leyendo del catálogo
  publicado, en vivo desde el navegador.
* Colores: la planilla de costos no los tiene. Se traen del catálogo publicado
  cruzando por código, así el cliente los sigue viendo.

Uso:
    python3 build.py                 # regenera las páginas al lado del script
    python3 build.py --out ../sitio  # las escribe en otra carpeta
    python3 build.py --dry-run       # solo muestra qué leyó, no escribe nada
"""
import sys, re, time, json, shutil, pathlib, urllib.request, warnings, csv, io
warnings.filterwarnings("ignore")
# sheets.py y la credencial viven al lado del script o en la carpeta de arriba
# (local: ~/Desktop/claude · en CI: la raíz del repo)
_aqui = pathlib.Path(__file__).resolve().parent
for _d in (_aqui, _aqui.parent):
    if (_d / "sheets.py").exists():
        sys.path.insert(0, str(_d)); break
import sheets

COSTOS = "1lMsQ_WMxlKZGT_EZPohpu28Zq9WUgaXZ32UOxd3yaNE"
PUB = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vQSAbORWkzoQ-0MXJ1ykvdpvd"
       "AbCop-S-9M7Jh9bnjaZGkLOH0lDGYMSEm3VaMzNWJ0Qk65gAEU7t1n/pub")
WIN_GID = "661876936"

# key          etiqueta            pestaña de costos            parser  gid del catálogo (colores)
CATS = [
    ("iphone",    "iPhone",           "Celulares",                 "gen", "417290024"),
    ("macbook",   "MacBook",          "MacBook",                   "mac", "97413136"),
    ("windows",   "Windows",          None,                        "win", None),
    ("ipad",      "iPad",             "iPad",                      "gen", "397123973"),
    ("imac",      "iMac · Mac mini",  "iMac - Mac Mini & Studio",  "gen", "1739381259"),
    ("watch",     "Watch",            "Watch",                     "gen", "966539432"),
    ("accesorios","Accesorios Apple", "Accesorios Apple",          "gen", "840295081"),
    ("samsung",   "Samsung",          "Samsung",                   "gen", "1897995502"),
    ("dji",       "DJI",              "DJI",                       "gen", "1621130278"),
    ("sonos",     "SONOS",            "Sonos",                     "gen", "1874994252"),
    ("otros",     "Otros",            "Otros",                     "gen", "1976460266"),
]

# Encabezados que nunca son el título de un bloque ni una descripción
EXC = {"codigo", "código", "mayorista", "unit cost", "profit", "tato", "melman",
       "otros", "prov otro", "belgrano", "precio ars", "precio usd"}
SIN_STOCK = ("ingresando", "sin stock", "consultar", "#n/a", "#value", "#ref")

def estado_de(precio):
    """Qué se le muestra al cliente cuando no hay precio publicable.
    Se respeta lo que dice la planilla; si la celda está vacía, es sin stock."""
    t = precio.strip()
    if not t or t.lower().startswith("#"):
        return "Sin stock"
    return t.capitalize() if t.isupper() else t

# La planilla escribe la capacidad de varias formas: "256GB", "512 GB ", "1TB GB".
SOLO_CAP = re.compile(r"^\s*(\d+)\s*(GB|TB)(\s*GB)?\s*$", re.I)


def normalizar(desc):
    m = SOLO_CAP.match(desc)
    return f"{m.group(1)} {m.group(2).upper()}" if m else desc


def parse_costos(rows):
    """Cada bloque arranca con una fila que tiene 'Unit Cost'. El precio de venta es
    la columna anterior (salteando MAYORISTA) y la descripción, la anterior a esa."""
    items, grupo, pi, di = [], None, -1, -1
    for raw in rows:
        c = [(x or "").strip() for x in raw] + [""] * 14
        if any(x.lower() == "unit cost" for x in c):
            u = next(i for i, x in enumerate(c) if x.lower() == "unit cost")
            j = u - 1
            while j > 0 and c[j].lower() in ("mayorista", "profit"):
                j -= 1
            pi, di = j, j - 1
            grupo = c[di] if c[di] and c[di].lower() not in EXC else \
                    next((x for x in c if x and x.lower() not in EXC), "")
            grupo = " ".join(grupo.split())
            continue
        if not grupo or pi < 0:
            continue
        desc, precio = c[di], c[pi]
        # Una fila sin precio igual es un producto: se lista como sin stock. Se pide
        # código para no arrastrar filas sueltas que no son productos.
        if not desc or desc.lower() in EXC or not (c[0] or precio):
            continue
        hay = bool(precio) and not any(m in precio.lower() for m in SIN_STOCK)
        item = {"codigo": c[0], "model": grupo,
                "desc": normalizar(" ".join(desc.split())), "avail": hay}
        if hay:
            item["price"] = " ".join(precio.split())
        else:
            item["estado"] = estado_de(precio)
        items.append(item)
    return items


def leer_pestana(pestana, intentos=4):
    """Google limita las lecturas por minuto. Si pega el tope (429), espera y
    reintenta en vez de abortar la publicación."""
    for n in range(intentos):
        try:
            return sheets.tab(COSTOS, pestana).get_all_values()
        except Exception as e:
            if "429" not in str(e) or n == intentos - 1:
                raise
            espera = 20 * (n + 1)
            print(f"    ⚠ tope de lecturas de Google, reintento en {espera}s")
            time.sleep(espera)


def bajar(url, intentos=3):
    """Google a veces corta la respuesta a la mitad (IncompleteRead). Con timeout y
    reintentos, en vez de quedarse colgado."""
    for n in range(intentos):
        try:
            return urllib.request.urlopen(url, timeout=20).read().decode("utf-8")
        except Exception as e:
            if n == intentos - 1:
                print(f"    ⚠ no se pudo bajar ({type(e).__name__}), sigo sin eso")
                return None
            time.sleep(2 * (n + 1))


def colores_publicados(gid):
    """código -> lista de colores, leídos del catálogo que ya está publicado.
    Si falla, se sigue sin colores: no vale abortar la publicación por esto."""
    texto = bajar(f"{PUB}?gid={gid}&single=true&output=csv")
    if not texto:
        return {}
    rows = list(csv.reader(io.StringIO(texto)))
    ci, out, actual = None, {}, []
    for r in rows:
        low = [(x or "").strip().lower() for x in r]
        if "colores" in low:
            ci = low.index("colores"); actual = []; continue
        if ci is None or ci >= len(r):
            continue
        if (r[ci] or "").strip():
            actual = [x.strip() for x in r[ci].split("\n") if x.strip()]
        for cell in r:
            cod = (cell or "").strip()
            if actual and cod and cod.isupper() and cod.isalnum() and 4 <= len(cod) <= 18:
                out[cod] = actual
    return out


def main():
    dry = "--dry-run" in sys.argv
    cuenta = {}
    here = pathlib.Path(__file__).resolve().parent
    salida = here
    if "--out" in sys.argv:                      # dónde escribir los HTML
        salida = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
        salida.mkdir(parents=True, exist_ok=True)
    datos, resumen = {}, []

    for key, label, pestana, parser, gid in CATS:
        if parser == "win":
            # Windows se lee en vivo en el navegador; acá solo se cuenta para la portada
            texto = bajar(f"{PUB}?gid={WIN_GID}&single=true&output=csv")
            filas = list(csv.reader(io.StringIO(texto))) if texto else []
            cuenta[key] = sum(1 for r in filas if len(r) > 1 and r[1].strip())
            resumen.append(f"{label:18} {cuenta[key]:3} productos · en vivo desde el catálogo")
            continue
        items = parse_costos(leer_pestana(pestana))
        col = colores_publicados(gid) if gid else {}
        pegados = 0
        for i in items:
            c = col.get(i["codigo"])
            if c:
                i["colors"] = c; pegados += 1
            i.pop("codigo", None)
        datos[key] = items
        cuenta[key] = len(items)
        resumen.append(f"{label:18} {len(items):3} productos · "
                       f"{len(set(i['model'] for i in items))} bloques · {pegados} con colores")

    for linea in resumen:
        print(" ", linea)
    if dry:
        print("\n--dry-run: no se escribió nada.")
        return

    tpl = (here / "_template.html").read_text()

    # El ícono va incrustado en el HTML (data URI) y no como archivo suelto: así
    # viaja con la página a cualquier repo/subdominio sin tener que copiarlo.
    # El ícono va como ARCHIVO, no incrustado: Safari, los marcadores y los
    # buscadores ignoran los data: URI y piden /favicon.ico directamente.
    # Las rutas son relativas para que funcionen igual bajo el dominio propio
    # que bajo tptecno.github.io/catalogo/.
    for archivo in ("favicon.ico", "tp-32.png", "tp-180.png"):
        shutil.copy(here / "marca" / archivo, salida / archivo)
    favicon = ('<link rel="icon" href="favicon.ico" sizes="any">\n'
               '<link rel="icon" type="image/png" sizes="32x32" href="tp-32.png">\n'
               '<link rel="apple-touch-icon" href="tp-180.png">\n'
               '<meta name="theme-color" content="#FF395D">')
    tpl = tpl.replace("__FAVICON__", favicon)
    cats_js = json.dumps([
        {"key": k, "label": lb, "parser": p, "n": cuenta.get(k, 0),
         **({"mode": "json"} if p != "win" else
            {"mode": "csv", "url": f"{PUB}?gid={WIN_GID}&single=true&output=csv"})}
        for k, lb, _, p, _ in CATS], ensure_ascii=False, indent=2)
    bloques = "\n".join(
        f'<script type="application/json" id="datos-{k}">{json.dumps(v, ensure_ascii=False)}</script>'
        for k, v in datos.items())

    for fname, default in [("index.html", ""), ("iphone.html", "iphone"),
                           ("macbook.html", "macbook"), ("windows.html", "windows")]:
        lb = next((x for k, x, _, _, _ in CATS if k == default), "TPTecno")
        html = (tpl.replace("__TITULO__", lb).replace("__CATS__", cats_js)
                   .replace("__DEFAULT__", default)
                   .replace("__CAT__", next((p for k, _, _, p, _ in CATS if k == default), "gen"))
                   .replace("__FALLBACKS__", bloques))
        (salida / fname).write_text(html)
        print(f"  {fname:14} {len(html)//1024} KB")

    demo = (salida / "index.html").read_text()
    for tag in ['<!doctype html>', '<html lang="es">', "<head>", "</head>", "<body>",
                "</body>", "</html>", '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width,initial-scale=1">',
                '<meta name="robots" content="noindex">']:
        demo = demo.replace(tag, "")
    demo = demo.replace("<title>Catálogo iPhone · TPTecno</title>", "<title>Catálogo TPTecno</title>")
    demo = demo.replace('<div id="stale" class="stale"></div>',
                        '<div class="demo">Vista de demostración. Los precios salen de la planilla '
                        'de costos y quedan fijos en esta copia; publicada, la página se regenera '
                        'sola cada vez que se actualiza la planilla.</div>')
    demo = demo.replace("""  const s=document.getElementById("stale");
  s.style.display = local ? "block" : "none";
  if(local) s.textContent="Vista de prueba: no se pudo leer la planilla en vivo (pasa al abrir el archivo local). Se muestran los datos de la última copia.";
""", "")
    demo = demo.replace("""  .stale{display:none;background:#fff6e5;border:1px solid #f0d9a8;color:#7a5b12;
    border-radius:10px;padding:9px 12px;font-size:12.5px;margin-top:12px}""",
"""  .demo{background:#fff;border:1px solid var(--line);color:var(--muted);
    border-radius:10px;padding:10px 13px;font-size:12.5px;margin-top:14px;line-height:1.5}""")
    (salida / "demo_socio.html").write_text('<meta charset="utf-8">\n' + demo.strip())
    print(f"  demo_socio.html {len(demo)//1024} KB (para compartir)")


main()
