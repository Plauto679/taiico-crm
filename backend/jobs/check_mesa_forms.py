"""Check published official forms; never activate an unreviewed mapping."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from services.mesa_documents import check_official_form
from services.mesa_claims import check_sources

if __name__ == '__main__':
    result = check_official_form()
    print(result['status'] + ': ' + result['notice'])
    claims = check_sources()
    print('Reembolso: ' + claims['status'] + ': ' + claims['notice'])
    hospital_states = [check_sources(workflow) for workflow in ('cirugia_programada_gmm', 'pago_directo_gmm')]
    for workflow, state in zip(('Cirugía programada', 'Pago directo'), hospital_states):
        print(workflow + ': ' + state['status'] + ': ' + state['notice'])
    sys.exit(0 if all(state['status'] == 'verified' for state in [result, claims, *hospital_states]) else 1)
