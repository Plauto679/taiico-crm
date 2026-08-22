import io
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Campaign
from services.campanas import bounce_recipients, build_gmm_audience, parse_gmm_campaign_source, prepare_campaign_deliveries, render_template


def workbook_bytes(rows):
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False, sheet_name="GMM")
    return output.getvalue()


class CampaignTests(unittest.TestCase):
    def test_parse_and_filter_active_high_deductible_policies(self):
        parsed = parse_gmm_campaign_source(workbook_bytes([
            {"CONTRATANTE": "Cliente Uno", "RFC": "RFC010101AAA", "PRODUCTO": "MEDICALIFE", "NPOLIZA": "100", "FFINVIG": "20270101", "DEDUCIBLE": "$1,000,000", "NOMBRE": "/AGENTE/UNO", "Email": ""},
            {"CONTRATANTE": "Cliente Dos", "RFC": "RFC020202BBB", "PRODUCTO": "MEDICALIFE", "NPOLIZA": "200", "FFINVIG": "20240101", "DEDUCIBLE": "2000000", "NOMBRE": "AGENTE DOS", "Email": ""},
        ]))
        with patch("services.campanas._source_rows", return_value=parsed), patch(
            "services.campanas._client_directories", return_value=({}, {})
        ):
            audience = build_gmm_audience(Decimal("1000000"), today=date(2026, 8, 21))
        self.assertEqual(audience["summary"]["policies"], 1)
        self.assertEqual(audience["rows"][0]["numero_poliza"], "100")
        self.assertEqual(audience["rows"][0]["agente"], "AGENTE UNO")

    def test_render_safe_variables_and_report_missing_values(self):
        rendered, missing = render_template(
            "Hola {{nombre_cliente}}, póliza {{numero_poliza}} · {{agente}}",
            {"nombre_cliente": "Ana", "numero_poliza": "123", "agente": "", "deducible": 1000000},
        )
        self.assertEqual(rendered, "Hola Ana, póliza 123 · ")
        self.assertEqual(missing, ["agente"])

    def test_prepare_freezes_deliveries_and_excludes_incomplete_recipients(self):
        campaign = Campaign(id="campaign-1", name="Prueba", subject="Hola {{nombre_cliente}}", body="Póliza {{numero_poliza}}", status="borrador", segment_json={})
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        audience = {"rows": [
            {"key": "1", "numero_poliza": "100", "rfc": "RFC1", "nombre_cliente": "Ana", "email": "ana@example.com"},
            {"key": "2", "numero_poliza": "200", "rfc": "RFC2", "nombre_cliente": "Beto", "email": ""},
        ]}
        with patch("services.campanas._campaign_audience", return_value=audience), patch(
            "services.campanas._delivery_report", return_value={"deliveries": [], "summary": {}}
        ):
            prepare_campaign_deliveries(db, campaign)
        statuses = [call.args[0].status for call in db.add.call_args_list]
        self.assertEqual(statuses, ["pendiente", "sin_correo"])
        self.assertEqual(campaign.status, "preparada")
        db.commit.assert_called_once()

    def test_bounce_parser_only_matches_known_campaign_recipient(self):
        raw = b"""From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>\r
Subject: Delivery Status Notification (Failure)\r
Content-Type: text/plain; charset=utf-8\r
\r
Delivery to client@example.com failed.\r
Final-Recipient: rfc822; client@example.com\r
Diagnostic-Code: smtp; 550 5.1.1 The email account does not exist\r
"""
        matched, diagnostic = bounce_recipients(raw, {"client@example.com", "other@example.com"})
        self.assertEqual(matched, {"client@example.com"})
        self.assertIn("550", diagnostic)

    def test_regular_email_is_not_treated_as_bounce(self):
        raw = b"From: client@example.com\r\nSubject: Gracias\r\n\r\nMensaje recibido"
        matched, _ = bounce_recipients(raw, {"client@example.com"})
        self.assertEqual(matched, set())


if __name__ == "__main__":
    unittest.main()
