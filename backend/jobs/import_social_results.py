"""Import exact MCP result rows. Usage: PYTHONPATH=backend .venv/bin/python backend/jobs/import_social_results.py file.json"""
import json,sys
from pathlib import Path
from services.social_results import init_schema,import_snapshot
init_schema()
import_snapshot(json.loads(Path(sys.argv[1]).read_text()))
print('Métricas de Metricool guardadas')
