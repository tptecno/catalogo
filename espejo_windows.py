#!/usr/bin/env python3
"""
Espeja la pestana Windows de la planilla Catalogo hacia costos!Windows.

Por que existe: Windows no se carga a mano, lo reescribe cada dia el pipeline de
Melman (rutina "Windows Update Daily" -> Catalogo!Windows_DATA -> Apps Script ->
Catalogo!Windows). Para que costos sea la unica fuente que leen el catalogo web y
Shopify, se copia el resultado aca. Se conserva el formato de bloques tal cual:
aplanarlo perderia las lineas de specs, que alimentan los filtros de los dos sitios.

Solo escribe si algo cambio. Si no, sale en silencio.
"""
import hashlib
import json
import os
import socket
import sys

from google.oauth2 import service_account
import google.auth.transport.requests as tr

socket.setdefaulttimeout(45)

CATALOGO = "1lpHmxnre-SaS2TzPStgsC88rSOBVLM7X8YzkS-Z6B0A"
COSTOS = "1lMsQ_WMxlKZGT_EZPohpu28Zq9WUgaXZ32UOxd3yaNE"
SELLO = os.path.expanduser("~/tptecno/.ultimo_windows")
API = "https://sheets.googleapis.com/v4/spreadsheets"


def sesion():
    cred = service_account.Credentials.from_service_account_file(
        os.path.expanduser("~/tptecno/gcloud_sa.json"),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return tr.AuthorizedSession(cred)


def main():
    s = sesion()
    r = s.get(f"{API}/{CATALOGO}/values/Windows",
              params={"majorDimension": "ROWS"}, timeout=40)
    r.raise_for_status()
    filas = r.json().get("values", [])

    if len(filas) < 50:
        print(f"espejo windows: origen sospechoso ({len(filas)} filas), no se copia")
        return 1

    filas = [(f + [""] * 6)[:6] for f in filas]
    firma = hashlib.sha256(json.dumps(filas, ensure_ascii=False).encode()).hexdigest()

    previa = ""
    if os.path.exists(SELLO):
        previa = open(SELLO).read().strip()
    if firma == previa:
        return 0                      # sin cambios, nada que hacer

    s.post(f"{API}/{COSTOS}/values/Windows!A1:F1000:clear", timeout=40).raise_for_status()
    r = s.put(f"{API}/{COSTOS}/values/Windows!A1",
              params={"valueInputOption": "RAW"}, json={"values": filas}, timeout=60)
    r.raise_for_status()

    with open(SELLO, "w") as f:
        f.write(firma)
    print(f"espejo windows: {len(filas)} filas copiadas a costos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
