"""Check published official forms; never activate an unreviewed mapping."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from services.mesa_documents import check_official_form

if __name__ == '__main__':
    result = check_official_form()
    print(result['status'] + ': ' + result['notice'])
    sys.exit(0 if result['status'] == 'verified' else 1)
