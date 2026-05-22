"""
test_pdf.py — Prueba manual del generador de PDFs de rAÍz

Uso:
    python test_pdf.py

Genera en la raíz del proyecto:
    test_estudiante.pdf
    test_orientador.pdf
"""

import sys
import os
import tomllib
import pathlib

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Secrets (igual que app.py usa st.secrets) ─────────────────────────────────
secrets = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))
API_KEY = secrets["GEMINI_API_KEY"]

# ── Gemini client ──────────────────────────────────────────────────────────────
from google import genai

MODEL = "gemini-3.1-flash-lite"
client = genai.Client(api_key=API_KEY)

# ── System instruction ─────────────────────────────────────────────────────────
system_instruction = (ROOT / "instrucciones.txt").read_text(encoding="utf-8").strip()

# ── DB + generador ─────────────────────────────────────────────────────────────
import database as db
import pdf_generator

ESTUDIANTE_ID = "ALC-9-2026-0001"


def main():
    estudiante = db.login_estudiante(ESTUDIANTE_ID)
    if estudiante is None:
        print(f"Error: no existe '{ESTUDIANTE_ID}' en raiz_local.db")
        sys.exit(1)

    print(f"Estudiante : {estudiante['nombre']} {estudiante['apellido']} ({ESTUDIANTE_ID})")

    historial = db.get_historial(estudiante["id"])
    print(f"Mensajes   : {len(historial)}")

    print("Generando PDFs con Gemini...")
    pdf_est, pdf_ori = pdf_generator.generar_pdfs(
        estudiante, historial, client, MODEL, system_instruction
    )

    dest_est = ROOT / "test_estudiante.pdf"
    dest_ori = ROOT / "test_orientador.pdf"

    dest_est.write_bytes(pdf_est)
    print(f"Guardado   : {dest_est}")

    dest_ori.write_bytes(pdf_ori)
    print(f"Guardado   : {dest_ori}")


if __name__ == "__main__":
    main()
