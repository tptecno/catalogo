#!/usr/bin/env python3
"""
Helper de Google Sheets por API (lectura + ESCRITURA) — reutilizable para cualquier planilla.

Usa una credencial de SERVICE ACCOUNT (un JSON que se crea 1 sola vez en Google Cloud).
Una vez seteada, Claude puede leer/escribir cualquier sheet que esté compartida con el
email del service account (o que esté dentro de una carpeta de Drive compartida con él).

NO mueve dinero. Solo lee y escribe celdas de planillas.

Setup (1 vez): ver README_SHEETS.md.
Credencial: gcloud_sa.json en esta carpeta (o ruta en GOOGLE_SA_JSON de .env.cfo).

Uso CLI:
  python sheets.py whoami                      # email del service account (para compartirle las hojas)
  python sheets.py tabs <sheet_id>             # lista las pestañas
  python sheets.py read <sheet_id> <pestaña> [rango]   # imprime valores (ej. rango "A1:B20")
  python sheets.py set  <sheet_id> <pestaña> <celda> <valor>   # escribe UNA celda (ej. B674 1160)

Como módulo (lo que usa Claude para trabajar):
  import sheets
  ws = sheets.tab(sheet_id, "USD Value")
  sheets.read(ws, "A1:B5")
  sheets.write_col(ws, "B945", [1425, 1420, ...])   # escribe una columna desde B945 hacia abajo
  sheets.update(ws, "B2", [[560]])                  # batch update genérico
"""
import os, sys, json

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]


def _sa_path():
    # 1) GOOGLE_SA_JSON en .env.cfo  2) gcloud_sa.json en esta carpeta
    base = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base, ".env.cfo")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("GOOGLE_SA_JSON=") and "=" in line:
                p = line.split("=", 1)[1].strip().strip('"').strip("'")
                if p:
                    return p if os.path.isabs(p) else os.path.join(base, p)
    return os.path.join(base, "gcloud_sa.json")


def client():
    """Devuelve un cliente gspread autenticado con el service account."""
    import gspread
    from google.oauth2.service_account import Credentials
    path = _sa_path()
    if not os.path.exists(path):
        sys.exit(f"Falta la credencial del service account ({path}).\n"
                 f"Seguí README_SHEETS.md para crearla (1 sola vez).")
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def sa_email():
    path = _sa_path()
    if not os.path.exists(path):
        return None
    return json.load(open(path)).get("client_email")


def book(sheet_id):
    return client().open_by_key(sheet_id)


def tab(sheet_id, title):
    return book(sheet_id).worksheet(title)


def read(ws, rng=None):
    return ws.get_values(rng) if rng else ws.get_all_values()


def update(ws, start_cell, values_2d):
    """Batch update genérico. values_2d = lista de filas. USER_ENTERED respeta formatos/fechas."""
    # gspread 6.x: la firma es update(values, range_name), valores primero.
    return ws.update(values_2d, start_cell, value_input_option="USER_ENTERED")


def batch(sheet_id, pairs):
    """Escribe muchos rangos de una sola vez. pairs = [("Pestaña!A1", [[v]]), ...]"""
    return book(sheet_id).values_batch_update({
        "valueInputOption": "USER_ENTERED",
        "data": [{"range": r, "values": v} for r, v in pairs],
    })


def write_col(ws, start_cell, values):
    """Escribe una columna (lista de valores) desde start_cell hacia abajo, en UNA llamada."""
    return update(ws, start_cell, [[v] for v in values])


# ---------------- CLI ----------------
def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    cmd = a[0]
    if cmd == "whoami":
        em = sa_email()
        print(em or "(sin credencial todavía — ver README_SHEETS.md)")
        if em:
            print("→ Compartí tus planillas (o la carpeta de Drive) con ese email como Editor.")
    elif cmd == "tabs":
        for ws in book(a[1]).worksheets():
            print(f"{ws.title}  (filas {ws.row_count} x cols {ws.col_count})")
    elif cmd == "read":
        ws = tab(a[1], a[2])
        rng = a[3] if len(a) > 3 else None
        for row in read(ws, rng):
            print(row)
    elif cmd == "set":
        ws = tab(a[1], a[2])
        update(ws, a[3], [[a[4]]])
        print(f"OK {a[2]}!{a[3]} = {a[4]}")
    else:
        print("Comando no reconocido."); print(__doc__)


if __name__ == "__main__":
    main()
