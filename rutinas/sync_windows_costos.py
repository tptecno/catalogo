#!/usr/bin/env python3
"""
Melman (XLSX publicado) -> pestana Windows de la planilla de COSTOS.

Escribe directo en costos!Windows. No hay Apps Script de por medio: en costos no
existe el paso Windows_DATA -> Windows que si tiene el catalogo viejo.

Reconstruye la pestana DESDE CERO en cada corrida (borra y clona de nuevo)
para que la inyeccion de precios del paso final nunca vuelva a leer una celda
ya procesada: si se agrega contenido sobre una hoja vieja con formulas, esas
celdas siguen mostrando "USD ..." por el formato de moneda heredado y el
detector las vuelve a tomar como precio crudo, duplicando el markup. Por eso
NO se agrega nada de forma incremental: siempre se tira todo y se arma de
nuevo en una sola pasada.

Credencial: variable GOOGLE_SA_JSON con la ruta, o gcloud_sa.json en el cwd.
"""
import os
import re

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

COSTOS_ID = "1lMsQ_WMxlKZGT_EZPohpu28Zq9WUgaXZ32UOxd3yaNE"
MELMAN_XLSX_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQ6L61-q6LFrTt1F9BEwcWpQDAJmt2JVu7ZVB9WbHDG7TzaY0r5SWHJmQZl8Uobb1hU9wl7EBKZKkCV"
    "/pub?output=xlsx"
)
SHARED_DRIVE_ID = "0AIqU3CptK4JuUk9PVA"
HOJA_DESTINO = "Windows"
# Nombre propio del archivo temporal: la rutina del catalogo viejo barre TODOS los
# que se llaman "Temporary_Sync_Buffer". Si las dos usaran el mismo nombre y llegaran
# a solaparse, una le borraria el buffer a la otra en plena corrida.
BUFFER = "Temporary_Sync_Buffer_Costos"
HOJAS_A_SUMAR = ["GAMER", "ALL IN ONE"]
BLOQUEADAS = ["IMAC", "MACBOOK", "MAC MINI", "MAC STUDIO", "IPHONE", "IPAD", "WATCH", "SAMSUNG"]
COL_COSTO = 5


def clean_price(price_str):
    if not price_str:
        return 0
    s = re.sub(r"[^\d]", "", str(price_str))
    try:
        return float(s)
    except ValueError:
        return 0


def filas_usadas(ws):
    valores = ws.get_all_values()
    while valores and not any(c.strip() for c in valores[-1]):
        valores.pop()
    return len(valores), valores


def main():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(
        os.environ.get("GOOGLE_SA_JSON", "gcloud_sa.json"), scopes=scopes)
    client = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    sh = client.open_by_key(COSTOS_ID)

    temp_id = None
    clones_pendientes = []

    def pegar_debajo(temp_sh, nombre_hoja, ws_data, fila_inicio):
        ws_fuente = temp_sh.worksheet(nombre_hoja)
        clon_id = ws_fuente.copy_to(COSTOS_ID)["sheetId"]
        clones_pendientes.append(clon_id)
        ws_clon = next(w for w in sh.worksheets() if w.id == clon_id)
        n, _ = filas_usadas(ws_clon)
        ancho = max(ws_data.col_count, ws_clon.col_count)
        if ws_data.row_count < fila_inicio + n + 10:
            ws_data.add_rows(fila_inicio + n + 10 - ws_data.row_count)
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=COSTOS_ID,
            body={"requests": [{"copyPaste": {
                "source": {"sheetId": clon_id, "startRowIndex": 0, "endRowIndex": n,
                           "startColumnIndex": 0, "endColumnIndex": ancho},
                "destination": {"sheetId": ws_data.id, "startRowIndex": fila_inicio,
                                "endRowIndex": fila_inicio + n,
                                "startColumnIndex": 0, "endColumnIndex": ancho},
                "pasteType": "PASTE_NORMAL"}}]},
        ).execute()
        sh.del_worksheet(ws_clon)
        clones_pendientes.remove(clon_id)
        return n

    try:
        total_pasos = 5 + len(HOJAS_A_SUMAR)
        print("1/%s Bajando Melman..." % total_pasos)
        local = "/tmp/melman_sync.xlsx"
        r = requests.get(MELMAN_XLSX_URL, timeout=90)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)

        print("2/%s Convirtiendo a Google Sheet..." % total_pasos)
        media = MediaFileUpload(
            local,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True,
        )
        temp = drive.files().create(
            body={"name": BUFFER,
                  "mimeType": "application/vnd.google-apps.spreadsheet",
                  "parents": [SHARED_DRIVE_ID]},
            media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        temp_id = temp["id"]
        temp_sh = client.open_by_key(temp_id)

        print("3/%s Clonando LAPTOP..." % total_pasos)
        ws_laptop = temp_sh.worksheet("LAPTOP")
        nueva_id = ws_laptop.copy_to(COSTOS_ID)["sheetId"]
        try:
            sh.del_worksheet(sh.worksheet(HOJA_DESTINO))
        except gspread.exceptions.WorksheetNotFound:
            pass
        ws_data = next(w for w in sh.worksheets() if w.id == nueva_id)
        ws_data.update_title(HOJA_DESTINO)
        n_laptop, _ = filas_usadas(ws_data)
        print("    LAPTOP: %s filas" % n_laptop)

        contadores = {"LAPTOP": n_laptop}
        fila_actual = n_laptop
        for i, nombre_hoja in enumerate(HOJAS_A_SUMAR):
            print("%s/%s Pegando %s debajo..." % (4 + i, total_pasos, nombre_hoja))
            n = pegar_debajo(temp_sh, nombre_hoja, ws_data, fila_actual)
            contadores[nombre_hoja] = n
            fila_actual += n
            print("    %s: %s filas" % (nombre_hoja, n))

        print("%s/%s Validando..." % (4 + len(HOJAS_A_SUMAR), total_pasos))
        total, valores = filas_usadas(ws_data)
        muestra = " ".join(str(f[0]) for f in valores[:10]).upper()
        for b in BLOQUEADAS:
            if b in muestra:
                raise SystemExit("ABORTADO: aparecio '%s' donde iban laptops Windows." % b)
        if total < 50:
            raise SystemExit("ABORTADO: %s quedo con %s filas, sospechoso." % (HOJA_DESTINO, total))
        print("    OK, %s filas" % total)

        print("%s/%s Inyectando precios y ocultando costo..." % (total_pasos, total_pasos))
        updates = []
        for i, fila in enumerate(valores):
            n = i + 1
            if len(fila) < 2 or "USD" not in str(fila[1]).upper():
                continue
            costo = clean_price(fila[1])
            if costo > 50:
                updates.append({"range": "B%s" % n, "values": [[
                    "=IF(ISNUMBER(F{n});IF(F{n}>=3000;F{n}+300;IF(F{n}>=2000;F{n}+200;"
                    "IF(F{n}>=1000;F{n}+150;F{n}+120)));F{n})".format(n=n)]]})
                updates.append({"range": "F%s" % n, "values": [[costo]]})
        if updates:
            ws_data.batch_update(updates, value_input_option="USER_ENTERED")
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=COSTOS_ID,
            body={"requests": [{"updateDimensionProperties": {
                "range": {"sheetId": ws_data.id, "dimension": "COLUMNS",
                          "startIndex": COL_COSTO, "endIndex": COL_COSTO + 1},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}}]},
        ).execute()

        # Dejar la hoja EXACTAMENTE como queda Windows en el catalogo: 6 columnas,
        # el alto justo del contenido y los mismos anchos. El clon de Melman viene
        # de 1000x26 con todas las columnas en 100px.
        anchos = [(0, 1072), (1, 87), (2, 48), (3, 100), (4, 100), (5, 100)]
        pedidos = [{"updateSheetProperties": {
            "properties": {"sheetId": ws_data.id,
                           "gridProperties": {"rowCount": total, "columnCount": 6}},
            "fields": "gridProperties.rowCount,gridProperties.columnCount"}}]
        for idx, px in anchos:
            pedidos.append({"updateDimensionProperties": {
                "range": {"sheetId": ws_data.id, "dimension": "COLUMNS",
                          "startIndex": idx, "endIndex": idx + 1},
                "properties": {"pixelSize": px}, "fields": "pixelSize"}})
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=COSTOS_ID, body={"requests": pedidos}).execute()

        detalle = " + ".join("%s %s" % (nombre, contadores[nombre])
                              for nombre in ["LAPTOP"] + HOJAS_A_SUMAR)
        print("LISTO: %s con %s filas (%s), %s precios inyectados."
              % (HOJA_DESTINO, total, detalle, len(updates) // 2))

    finally:
        for clon_id in list(clones_pendientes):
            try:
                sheets.spreadsheets().batchUpdate(
                    spreadsheetId=COSTOS_ID,
                    body={"requests": [{"deleteSheet": {"sheetId": clon_id}}]}).execute()
            except Exception:
                pass
        # Barrido: manda a papelera TODOS los buffers de ESTA rutina, no solo el de
        # esta corrida. Filtra por el nombre propio para no tocar los del catalogo.
        try:
            pendientes = drive.files().list(
                q="name contains '%s' and trashed=false" % BUFFER,
                fields="files(id)", pageSize=200,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute().get("files", [])
            limpiados = 0
            for f in pendientes:
                try:
                    drive.files().update(fileId=f["id"], body={"trashed": True},
                                         supportsAllDrives=True).execute()
                    limpiados += 1
                except Exception:
                    pass
            if limpiados:
                print("Temporales limpiados: %s" % limpiados)
            if len(pendientes) > limpiados:
                print("AVISO: quedaron %s temporales sin borrar." % (len(pendientes) - limpiados))
        except Exception as e:
            print("AVISO: fallo el barrido de temporales: %s" % e)


if __name__ == "__main__":
    main()
