import os
from pathlib import Path

from dotenv import load_dotenv

# Define base paths using pathlib for relative path resolution
# Current file is in: .../2025 - Antigravity CRM/taiico-crm/backend/config.py
# We want to reach: .../2025 - Antigravity CRM/

# Resolve the parent directory of the current file (backend)
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
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
    "RENOVACIONES": BASE_DIR / "Fechas de emision de Polizas y renovaciones" / "AARCO & AXA.xlsx",
}

PROMOTORIA_SURA_PATHS = {
    "RENOVACIONES": BASE_DIR / "Fechas de emision de Polizas y renovaciones" / "Promotoria SURA.xlsx",
}

CLIENT_EMAILS_PATH = BASE_DIR / "Correos de los clientes" / "Clientes Correos Taiico.xlsx"

USERS_DB = BASE_DIR / "Users" / "Users & Passwords.xlsx"

SHEET_NAMES = {
    "COBRANZA_VIDA": "Vida",
    "COBRANZA_GMM": "GMM",
    "CARTERA_VIDA": "Vida",
    "CARTERA_GMM": "GMM",
    "RENOVACIONES_VIDA": "Vida",
    "RENOVACIONES_GMM": "GMM",
}

GOOGLE_DRIVE_SHARED_DRIVE_ID = os.getenv("GOOGLE_DRIVE_SHARED_DRIVE_ID")

GOOGLE_DRIVE_SOURCE_FOLDERS = {
    "cobranza.metlife": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_METLIFE_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_METLIFE_FOLDER_ID"),
        "source_category": "cobranza",
        "insurer_id": "metlife",
        "product_branch": None,
        "parser_name": "metlife_cobranza_workbook",
        "filename_contains": "metlife",
    },
    "cobranza.sura": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_SURA_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_SURA_FOLDER_ID"),
        "source_category": "cobranza",
        "insurer_id": "sura",
        "product_branch": None,
        "parser_name": "sura_cobranza_workbook",
        "filename_contains": "sura",
    },
    "cobranza.aarco": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_AARCO_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_COBRANZA_AARCO_FOLDER_ID"),
        "source_category": "cobranza",
        "insurer_id": "aarco",
        "product_branch": None,
        "parser_name": None,
        "filename_contains": "aarco",
    },
    "renovaciones.aarco_axa": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_AARCO_AXA_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_FOLDER_ID"),
        "source_category": "renovaciones",
        "insurer_id": "aarco",
        "product_branch": None,
        "parser_name": None,
        "filename_contains": "aarco & axa",
    },
    "renovaciones.metlife_gmm": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_METLIFE_GMM_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_FOLDER_ID"),
        "source_category": "renovaciones",
        "insurer_id": "metlife",
        "product_branch": "GMM",
        "parser_name": "metlife_gmm_renewal_workbook",
        "filename_contains": "metlife gmm",
    },
    "renovaciones.metlife_vida": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_METLIFE_VIDA_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_FOLDER_ID"),
        "source_category": "renovaciones",
        "insurer_id": "metlife",
        "product_branch": "VIDA",
        "parser_name": "metlife_vida_renewal_workbook",
        "filename_contains": "metlife vida",
    },
    "renovaciones.promotoria_sura": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_PROMOTORIA_SURA_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_FOLDER_ID"),
        "source_category": "renovaciones",
        "insurer_id": "sura",
        "product_branch": None,
        "parser_name": None,
        "filename_contains": "promotoria sura",
    },
    "renovaciones.sura": {
        "file_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_SURA_FILE_ID"),
        "folder_id": os.getenv("GOOGLE_DRIVE_SOURCE_RENOVACIONES_FOLDER_ID"),
        "source_category": "renovaciones",
        "insurer_id": "sura",
        "product_branch": None,
        "parser_name": None,
        "filename_contains": "sura",
    },
}
