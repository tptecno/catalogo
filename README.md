# Catálogo TPTecno

Catálogo de precios para clientes, con filtros por categoría. Reemplaza al Google
Sheet publicado al que hoy redirigen los subdominios (`iphone.tptecno.com`,
`macbook.tptecno.com`, etc.).

## Qué hay acá

Los HTML de la raíz son el sitio que se publica:

| archivo | subdominio | filtros |
|---|---|---|
| `index.html`   | catalogo.tptecno.com | las 11 categorías, con navegación |
| `iphone.html`  | iphone.tptecno.com   | Almacenamiento |
| `macbook.html` | macbook.tptecno.com  | Línea · Tamaño · Chip · RAM · Almacenamiento |
| `windows.html` | windows.tptecno.com  | Tipo · Marca · RAM · Almacenamiento · Pantalla · Gráficos · Disponibilidad |

`index.html` también responde a `#iphone`, `#macbook`, `#windows`, `#ipad`… así que
alcanza con una sola página para linkear cualquier categoría.

## De dónde salen los precios

De la **planilla de costos**, que es donde nace el precio. De cada fila se toma solo
el código, la descripción y el precio de venta: las columnas MAYORISTA, Unit Cost,
Profit y las de cada proveedor **no entran al HTML**.

Windows es la excepción — no está en esa planilla, así que se sigue leyendo del
catálogo publicado, en vivo desde el navegador de quien abre la página.

Como la planilla de costos es privada, el navegador no la puede leer: las páginas se
generan con `generador/build.py`, que necesita `gcloud_sa.json` (la credencial del
service account, que no está en este repo y no debe estarlo).

    python3 generador/build.py --out .          # regenera el sitio
    python3 generador/build.py --dry-run        # solo muestra qué leyó

## Publicación

GitHub Pages sirve los HTML de la raíz. El workflow `publicar.yml` puede regenerarlos
solo; hoy está en modo manual hasta definir dónde vive la credencial.
