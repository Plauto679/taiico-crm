import os

# Define base paths
# Note: In a real deployment, these might be environment variables.

# Using the paths found in src/lib/config.ts
BASE_PATH = "/Users/albertoalfaromendoza/Library/CloudStorage/GoogleDrive-alberto.alfaro@taiico.com/Shared drives/Administrativos/2025 - Antigravity CRM"

METLIFE_PATHS = {
    "COBRANZA": os.path.join(BASE_PATH, "Bases de cobranza y comisiones/Metlife base cobranza.xlsx"),
    "CARTERA": os.path.join(BASE_PATH, "Relaciones de cartera/Cartera Metlife.xlsx"),
    "RENOVACIONES_VIDA": os.path.join(BASE_PATH, "Fechas de emision de Polizas y renovaciones/Metlife Vida.xlsx"),
    "RENOVACIONES_GMM": os.path.join(BASE_PATH, "Fechas de emision de Polizas y renovaciones/Metlife GMM.xlsx"),
}

SHEET_NAMES = {
    "COBRANZA_VIDA": "Vida",
    "COBRANZA_GMM": "GMM",
    "CARTERA_VIDA": "Vida",
    "CARTERA_GMM": "GMM",
    "RENOVACIONES_VIDA": "Vida",
    "RENOVACIONES_GMM": "GMM",
}
