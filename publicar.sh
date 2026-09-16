#!/bin/bash
# Regenera el catálogo desde la planilla de costos y lo publica.
#
#   ./publicar.sh          a mano
#
# Corre solo cada 15 minutos por launchd (com.tptecno.catalogo).
# Log: ~/Library/Logs/tptecno-catalogo.log
set -eo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ahora() { date '+%d/%m %H:%M:%S'; }

# La rutina de GitHub publica en el mismo repo: hay que traer lo suyo antes de
# generar, o el push de acá choca y el agente queda trabado.
git pull --rebase --autostash -q origin main 2>/dev/null || git reset --hard -q origin/main

../.venv/bin/python generador/build.py --out . >/tmp/catalogo_build.log 2>&1 || {
  echo "$(ahora)  ✗ falló la generación:"; tail -5 /tmp/catalogo_build.log; exit 1;
}

algo=0

# 1) El catálogo general. Solo se suben los HTML generados: una corrida desatendida
#    nunca publica cambios de código que alguien haya dejado a medias.
# windows.csv: los datos de Windows, que la página pide en vivo al propio sitio en
# vez de a Google. sync.csv: la lista plana que lee la rutina de Shopify. Los dos
# salen de costos y van SIN columnas de costo ni de proveedor.
PAGINAS="index.html iphone.html macbook.html windows.html windows.csv sync.csv favicon.ico tp-32.png tp-180.png"
# Se agrega ANTES de comparar: `git diff` a secas no ve los archivos nuevos, así que
# un archivo recién creado (pasó con windows.csv y sync.csv) nunca se publicaría.
git add $PAGINAS
if ! git diff --cached --quiet -- $PAGINAS; then
  cambios=$(git diff --cached --stat -- $PAGINAS | tail -1)
  git commit -qm "Actualización de precios $(date '+%d/%m/%Y %H:%M')"
  git push -q origin main
  echo "$(ahora)  ✓ catálogo publicado ($cambios)"
  algo=1
fi

# 2) Los subdominios propios. Va un repo por dominio porque GitHub Pages admite un
#    solo dominio propio por repositorio. Se comparan aparte del principal, así uno
#    que quedó atrasado se pone al día aunque el catálogo no haya cambiado.
publicar_subdominio() {   # $1 = repo en ~/tptecno   $2 = página que va como index
  local repo="$HOME/tptecno/$1"
  [ -d "$repo/.git" ] || return 0
  cp "$2" "$repo/index.html"
  cp favicon.ico tp-32.png tp-180.png "$repo/"
  # La página de Windows pide windows.csv al mismo sitio, así que el subdominio
  # necesita su propia copia o queda sin datos.
  extra=""
  if [ "$1" = windows ]; then
    cp windows.csv "$repo/"
    extra="windows.csv"
  fi
  git -C "$repo" add index.html favicon.ico tp-32.png tp-180.png $extra
  if ! git -C "$repo" diff --cached --quiet; then
    git -C "$repo" commit -qm "Actualización de precios $(date '+%d/%m/%Y %H:%M')"
    git -C "$repo" push -q origin main
    echo "$(ahora)  ✓ $1 actualizado"
    algo=1
  fi
}

publicar_subdominio windows windows.html

[ "$algo" = 0 ] && echo "$(ahora)  · sin cambios"
exit 0
