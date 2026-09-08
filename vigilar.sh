#!/bin/bash
# Vigila la planilla de costos y publica SOLO cuando cambió algo.
#
# Corre cada minuto por launchd (com.tptecno.catalogo). La consulta es una sola
# llamada a Google que pregunta "¿cuándo se modificó por última vez?" — no baja la
# planilla. Si no cambió nada, termina en menos de un segundo y no escribe nada.
#
# Cada 6 horas publica igual, aunque no haya cambios: es la red de seguridad por si
# se pierde el archivo de estado o el sitio quedó desincronizado por otra razón.
set -eo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ESTADO="$HOME/tptecno/.ultimo_cambio"
SELLO="$HOME/tptecno/.ultima_publicacion"
MAX_SEGUNDOS=21600          # 6 horas

ahora() { date '+%d/%m %H:%M:%S'; }

# Si quedó un generador colgado de una corrida anterior, se lo mata: mientras viva,
# launchd no lanza esta tarea de nuevo y el catálogo se congela sin aviso.
for viejo in $(pgrep -f "generador/build.py" || true); do
  minutos=$(ps -o etime= -p "$viejo" | tr -d ' ' | awk -F: '{ if (NF==3) print $1*60; else print $1 }')
  if [ "${minutos:-0}" -ge 10 ] 2>/dev/null; then
    kill -9 "$viejo" 2>/dev/null && echo "$(ahora)  ⚠ había un generador colgado, lo reinicié"
  fi
done

# Marca de tiempo de la última edición de la planilla de costos
marca=$(../.venv/bin/python - 2>/dev/null <<'PY'
import warnings, os; warnings.filterwarnings("ignore")
from google.oauth2 import service_account
import google.auth.transport.requests as tr
cred=service_account.Credentials.from_service_account_file(
    os.path.expanduser("~/tptecno/gcloud_sa.json"),
    scopes=["https://www.googleapis.com/auth/drive.readonly"])
s=tr.AuthorizedSession(cred)
r=s.get("https://www.googleapis.com/drive/v3/files/1lMsQ_WMxlKZGT_EZPohpu28Zq9WUgaXZ32UOxd3yaNE",
        params={"fields":"modifiedTime"}, timeout=20)
r.raise_for_status()
print(r.json()["modifiedTime"])
PY
) || {           # sin internet o Google caído: se reintenta en un minuto
  # Se avisa como mucho una vez por hora, para no llenar el registro
  FALLO="$HOME/tptecno/.ultimo_fallo"
  ult=$(cat "$FALLO" 2>/dev/null || echo 0)
  if [ $(( $(date +%s) - ult )) -gt 3600 ]; then
    echo "$(ahora)  ✗ no se pudo consultar la planilla"; date +%s > "$FALLO"
  fi
  exit 0
}

[ -z "$marca" ] && exit 0

previa=$(cat "$ESTADO" 2>/dev/null || echo "")
ultima=$(cat "$SELLO" 2>/dev/null || echo 0)
transcurrido=$(( $(date +%s) - ultima ))

if [ "$marca" = "$previa" ] && [ "$transcurrido" -lt "$MAX_SEGUNDOS" ]; then
  exit 0                                   # nada que hacer
fi

if [ "$marca" != "$previa" ]; then
  echo "$(ahora)  → cambio detectado en la planilla"
fi

./publicar.sh
echo "$marca" > "$ESTADO"
date +%s > "$SELLO"
