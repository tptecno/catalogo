#!/bin/bash
# Regenera el catálogo desde la planilla de costos y lo publica.
#   ./publicar.sh
# Tarda ~1 minuto: ~30s de leer la planilla, ~35s de GitHub Pages.
set -e
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"

echo "→ Leyendo la planilla de costos…"
../.venv/bin/python generador/build.py --out .

if git diff --quiet; then
  echo "✓ Sin cambios: el catálogo publicado ya está al día."
  exit 0
fi

echo "→ Subiendo…"
git add -A
git commit -qm "Actualización de precios $(date '+%d/%m/%Y %H:%M')"
git push -q origin main
echo "✓ Listo. En ~35 segundos queda en https://tptecno.github.io/catalogo/"
