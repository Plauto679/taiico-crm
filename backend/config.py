import os
from pathlib import Path

# Define base paths using pathlib for relative path resolution
# Current file is in: .../2025 - Antigravity CRM/taiico-crm/backend/config.py
# We want to reach: .../2025 - Antigravity CRM/

# Resolve the parent directory of the current file (backend)
BACKEND_DIR = Path(__file__).resolve().parent
# Resolve the project root (taiico-crm)
PROJECT_ROOT = BACKEND_DIR.parent
# Resolve the shared drive root (2025 - Antigravity CRM)
BASE_DIR = PROJECT_ROOT.parent

METLIFE_PATHS = {
    "COBRANZA": BASE_DIR / "Bases de cobranza y comisiones" / "Metlife base cobranza.xlsx",
    "CARTERA": BASE_DIR / "Relaciones de cartera" / "Cartera Metlife.xlsx",
    "RENOVACIONES_VIDA": BASE_DIR / "Fechas de emision de Polizas y renovaciones" / "Metlife Vida.xlsx",
    "RENOVACIONES_GMM": BASE_DIR / "Fechas de emision de Polizas y renovaciones" / "Metlife GMM.xlsx",
}

SURA_PATHS = {
    "RENOVACIONES": BASE_DIR / "Fechas de emision de Polizas y renovaciones" / "SURA.xlsx",
    "COBRANZA": BASE_DIR / "Bases de cobranza y comisiones" / "SURA base cobranza.xlsx",
    "CARTERA": BASE_DIR / "Relaciones de cartera" / "Cartera SURA.xlsx",
}

AARCO_PATHS = {
    "COBRANZA": BASE_DIR / "Bases de cobranza y comisiones" / "AARCO base cobranza.xlsx",
}

USERS_DB = BASE_DIR / "Users" / "Users & Passwords.xlsx"

SHEET_NAMES = {
    "COBRANZA_VIDA": "Vida",
    "COBRANZA_GMM": "GMM",
    "CARTERA_VIDA": "Vida",
    "CARTERA_GMM": "GMM",
    "RENOVACIONES_VIDA": "Vida",
    "RENOVACIONES_GMM": "GMM",
}
