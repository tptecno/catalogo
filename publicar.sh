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

../.venv/bin/python generador/build.py --out . >/tmp/catalogo_build.log 2>&1 || {
  echo "$(ahora)  ✗ falló la generación:"; tail -5 /tmp/catalogo_build.log; exit 1;
}

algo=0

# 1) El catálogo general. Solo se suben los HTML generados: una corrida desatendida
#    nunca publica cambios de código que alguien haya dejado a medias.
PAGINAS="index.html iphone.html macbook.html windows.html"
if ! git diff --quiet -- $PAGINAS; then
  cambios=$(git diff --stat -- $PAGINAS | tail -1)
  git add $PAGINAS
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
  if ! git -C "$repo" diff --quiet -- index.html; then
    git -C "$repo" add index.html
    git -C "$repo" commit -qm "Actualización de precios $(date '+%d/%m/%Y %H:%M')"
    git -C "$repo" push -q origin main
    echo "$(ahora)  ✓ $1 actualizado"
    algo=1
  fi
}

publicar_subdominio windows windows.html

[ "$algo" = 0 ] && echo "$(ahora)  · sin cambios"
exit 0
