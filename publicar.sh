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

# Solo se publican los HTML generados: una corrida desatendida nunca sube
# cambios de código que alguien haya dejado a medias.
PAGINAS="index.html iphone.html macbook.html windows.html"
if git diff --quiet -- $PAGINAS; then
  echo "$(ahora)  · sin cambios"
  exit 0
fi

cambios=$(git diff --stat -- $PAGINAS | tail -1)
git add $PAGINAS
git commit -qm "Actualización de precios $(date '+%d/%m/%Y %H:%M')"
git push -q origin main
echo "$(ahora)  ✓ publicado ($cambios)"
