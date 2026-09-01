import sys
import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Client, ClientPromotoria
from services.client_registry_mirror import _workbook_bytes


class ClientRegistryMirrorTests(unittest.TestCase):
    def test_workbook_contains_promotorias_and_drive_link(self):
        client = Client(
            id="client",
            full_name="Cliente Ejemplo",
            rfc="AAA010101AAA",
            email="cliente@example.com",
            status="active",
            identity_status="identified",
            drive_folder_url="https://drive.google.com/drive/folders/example",
            drive_folder_name="AAA010101AAA - Cliente Ejemplo",
        )
        client.promotorias = [
            ClientPromotoria(promotoria="TAIICO", sources_json=[]),
            ClientPromotoria(promotoria="ABBONDANZA", sources_json=[]),
        ]

        workbook = load_workbook(BytesIO(_workbook_bytes([client])), data_only=True)
        values = list(workbook["Clientes"].values)

        self.assertEqual(values[0][4], "Promotorias")
        self.assertEqual(values[1][4], "ABBONDANZA, TAIICO")
        self.assertEqual(values[1][7], client.drive_folder_url)
        self.assertEqual(workbook["Control"]["B4"].value, "TAIICO CRM / tabla clients")


if __name__ == "__main__":
    unittest.main()
