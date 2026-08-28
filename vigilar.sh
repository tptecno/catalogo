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
) || exit 0        # sin internet o Google caído: se reintenta en un minuto

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
