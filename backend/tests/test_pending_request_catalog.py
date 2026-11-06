import re
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from services.auth import AccessProfile
from services import pendientes


class PendingRequestCatalogTests(unittest.TestCase):
    def test_frontend_options_match_backend(self):
        source = (Path(__file__).resolve().parents[2] / 'src/components/pendientes/RegisterPendingModal.tsx').read_text()
        for branch in ('GMM', 'VIDA'):
            block = re.search(rf'const {branch}_REQUESTS = \[(.*?)\];', source, re.S).group(1)
            self.assertEqual(set(re.findall(r"'([^']+)'", block)), getattr(pendientes, f'{branch}_REQUEST_OPTIONS'))

    def test_new_requests_reach_storage_with_exact_labels(self):
        profile = AccessProfile('test@example.com', 'admin', ('TAIICO',), '', ('*',), {'pendientes': 'operacion'})
        cases = [
            ('GMM', 'Corrección de nombre de asegurado GMM'),
            ('Vida', 'Corrección de nombre de asegurado VIDA'),
            ('Vida', 'Cancelación de pólizas VIDA'),
            ('Vida', 'Aportaciones adicionales fijas VIDA'),
            ('Vida', 'Aportaciones adicionales variables VIDA'),
            ('Vida', 'Aportaciones adicionales fijas VIDA, Corrección de nombre de asegurado VIDA'),
        ]
        for branch, label in cases:
            with self.subTest(label=label), \
                patch.object(pendientes, '_resolve_pending_master_client', return_value={'id': 'test-client', 'nombre': 'Cliente', 'rfc': ''}), \
                patch.object(pendientes, '_assigned_promotoria', return_value='TAIICO'), \
                patch.object(pendientes, '_assigned_agent_rfc', return_value='TEST'), \
                patch.object(pendientes, '_assigned_responsible', return_value=''), \
                patch.object(pendientes, '_create_pending_record', return_value={'ok': True}) as save:
                payload = pendientes.EmisionServiciosCreateRequest(asegurado='Cliente', casificacion=branch, tipo_tramite='Servicios', solicitud_de=label, promotoria='TAIICO', rfc_agente='TEST')
                pendientes.create_emision_servicios_pending(payload, BackgroundTasks(), profile)
                self.assertEqual(save.call_args.args[1]['Solicitud de'], label)

    def test_vida_contributions_not_accepted_as_gmm(self):
        payload = pendientes.EmisionServiciosCreateRequest(asegurado='Cliente', casificacion='GMM', tipo_tramite='Servicios', solicitud_de='Aportaciones adicionales fijas VIDA', promotoria='TAIICO', rfc_agente='TEST')
        with self.assertRaises(HTTPException) as result:
            pendientes.create_emision_servicios_pending(payload, BackgroundTasks(), None)
        self.assertEqual(result.exception.status_code, 422)
