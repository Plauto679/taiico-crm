import io
import sys
import unittest
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pendientes import (
    EmisionServiciosCreateRequest,
    GMM_REQUEST_OPTIONS,
    SiniestrosCreateRequest,
    VIDA_REQUEST_OPTIONS,
    PendingSource,
    _derived_day_values,
    _folder_name_for_row,
    add_pending_follow_up,
    append_pending_record,
    build_pending_report,
    pending_report_html,
    normalize_report_recipients,
    parse_pending_workbook,
    update_pending_record,
)
from services.pending_document_requirements import (
    GMM_DOCUMENT_REQUIREMENTS,
    VIDA_DOCUMENT_REQUIREMENTS,
    requirements_for,
    split_request_types,
)


def workbook_bytes(sheet_name, headers, rows):
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer:
        pd.DataFrame(rows, columns=headers).to_excel(
            writer,
            sheet_name=sheet_name,
            index=False,
        )
    return output.getvalue()


def workbook_with_table(sheet_name, headers, rows):
    document = Workbook()
    sheet = document.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    table = Table(displayName="Pendientes", ref=f"A1:{chr(64 + len(headers))}{len(rows) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    sheet.add_table(table)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class PendingWorkbookTests(unittest.TestCase):
    def test_summary_uses_core_columns_and_latest_update(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 2)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Folio", "Cliente", "15-jul", "16-jul"],
                [["123", "Cliente Uno", "Primer avance", "Último avance"]],
            ),
            source,
        )
        row = result["rows"][0]
        self.assertEqual(row["summary"], {"Folio": "123", "Cliente": "Cliente Uno"})
        self.assertEqual(row["latest_update"], {"date": "16-jul", "update": "Último avance"})
        self.assertEqual(len(row["history"]), 2)

    def test_empty_history_cells_are_not_shown_in_detail(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 1)
        result = parse_pending_workbook(
            workbook_bytes("Base", ["Folio", "15-jul", "16-jul"], [["123", "", "Avance"]]),
            source,
        )
        self.assertEqual(
            result["rows"][0]["history"],
            [{"date": "16-jul", "update": "Avance"}],
        )

    def test_latest_update_is_last_non_empty_comment_for_each_row(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 1)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Folio", "15-jul-26", "20-jul-26", "22-jul-26"],
                [
                    ["1", "En espera de aseguradora", "", ""],
                    ["2", "", "En espera de firma del cliente", ""],
                ],
            ),
            source,
        )
        self.assertEqual(result["rows"][0]["latest_update"], {"date": "15-jul-26", "update": "En espera de aseguradora"})
        self.assertEqual(result["rows"][1]["latest_update"], {"date": "20-jul-26", "update": "En espera de firma del cliente"})

    def test_follow_up_adds_one_date_column_and_updates_target_row(self):
        source = PendingSource("emision-servicios", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_bytes(
            "Base",
            ["Folio", "20-jul-26"],
            [["1", "Anterior"], ["2", ""]],
        )
        updated, header = add_pending_follow_up(
            original,
            source,
            3,
            "En espera de firma",
            date(2026, 7, 22),
        )
        parsed = parse_pending_workbook(updated, source)
        self.assertEqual(header, "22-jul-26")
        self.assertEqual(parsed["rows"][1]["latest_update"], {"date": header, "update": "En espera de firma"})

        with zipfile.ZipFile(io.BytesIO(original)) as before, zipfile.ZipFile(io.BytesIO(updated)) as after:
            changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        self.assertEqual(changed, ["xl/worksheets/sheet1.xml"])

    def test_second_follow_up_same_day_reuses_column(self):
        source = PendingSource("siniestros", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_bytes("Base", ["Folio", "21/07/2026"], [["1", ""]])
        first, header = add_pending_follow_up(original, source, 2, "Primer comentario", date(2026, 7, 22))
        second, second_header = add_pending_follow_up(first, source, 2, "Segundo comentario", date(2026, 7, 22))
        table = pd.read_excel(io.BytesIO(second), sheet_name="Base", dtype=str, keep_default_na=False)
        self.assertEqual(header, "22/07/2026")
        self.assertEqual(second_header, header)
        self.assertEqual(list(table.columns).count(header), 1)
        self.assertEqual(table.iloc[0][header], "Primer comentario | Segundo comentario")

    def test_follow_up_extends_native_excel_table(self):
        source = PendingSource("emision-servicios", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_with_table("Base", ["Folio", "21-jul-26"], [["1", "Anterior"]])
        updated, header = add_pending_follow_up(original, source, 2, "Nuevo", date(2026, 7, 22))
        with zipfile.ZipFile(io.BytesIO(updated)) as archive:
            table_xml = archive.read("xl/tables/table1.xml").decode()
        self.assertIn('ref="A1:C2"', table_xml)
        self.assertIn('count="3"', table_xml)
        self.assertIn(f'name="{header}"', table_xml)

    def test_append_pending_record_only_sets_requested_columns(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 3)
        original = workbook_bytes(
            "Base",
            ["Asegurado", "Póliza", "Casificacion", "16-jul"],
            [["Anterior", "123", "Vida", "Seguimiento"]],
        )
        updated, source_row = append_pending_record(original, source, {
            "Asegurado": "Nueva Persona",
            "Póliza": "456",
            "Casificacion": "GMM",
        })
        parsed = parse_pending_workbook(updated, source)
        self.assertEqual(source_row, 3)
        self.assertEqual(parsed["rows"][-1]["summary"], {
            "Asegurado": "Nueva Persona",
            "Póliza": "456",
            "Casificacion": "GMM",
        })
        self.assertEqual(parsed["rows"][-1]["latest_update"]["update"], "")

    def test_create_requests_allow_missing_rfc_and_policy(self):
        emision = EmisionServiciosCreateRequest(
            asegurado="Cliente",
            casificacion="GMM",
            tipo_tramite="Servicios",
            solicitud_de="Rehabilitación GMM",
        )
        siniestro = SiniestrosCreateRequest(
            asegurado="Cliente",
            tipo_tramite="Reembolso",
            tramite="Complemento",
        )
        self.assertEqual(emision.rfc, "")
        self.assertEqual(emision.poliza, "")
        self.assertEqual(siniestro.rfc, "")

    def test_update_pending_record_updates_and_clears_core_values(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 3)
        original = workbook_bytes(
            "Base",
            ["Asegurado", "RFC", "Póliza", "22-jul"],
            [["Cliente", "", "123", "Registrado"]],
        )
        updated = update_pending_record(
            original,
            source,
            2,
            {"RFC": "AAMA950203I52", "Póliza": ""},
        )
        row = parse_pending_workbook(updated, source)["rows"][0]
        self.assertEqual(row["summary"]["RFC"], "AAMA950203I52")
        self.assertEqual(row["summary"]["Póliza"], "")
        self.assertEqual(row["latest_update"]["update"], "Registrado")

    def test_folder_name_combines_rfc_and_request(self):
        self.assertEqual(
            _folder_name_for_row({
                "summary": {
                    "RFC": "aama950203i52",
                    "Solicitud de": "Rehabilitación póliza",
                },
            }),
            "AAMA950203I52 - Rehabilitación póliza",
        )

    def test_request_options_are_classification_specific(self):
        self.assertIn("Reembolso GMM", GMM_REQUEST_OPTIONS)
        self.assertNotIn("Reembolso GMM", VIDA_REQUEST_OPTIONS)
        self.assertIn("Rescate total / parcial VIDA", VIDA_REQUEST_OPTIONS)

    def test_rfc_is_preserved_as_core_column(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 3)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Asegurado", "RFC", "Póliza", "22-jul"],
                [["Cliente", "AAMA950203I52", "123", "Registrado"]],
            ),
            source,
        )
        self.assertEqual(result["rows"][0]["summary"]["RFC"], "AAMA950203I52")

    def test_emision_new_date_columns_remain_core_and_days_are_current(self):
        source = PendingSource("emision-servicios", "Test", "TEST_ID", "file", "Base", 15)
        headers = [
            "Folio", "Asegurado", "RFC", "Póliza", "Producto", "Agente",
            "Casificacion", "Tipo de Trámite", "Solicitud de", "Estatus actual",
            "Fecha Inicio", "Días Transcurridos", "Fecha ingreso en la aseguradora",
            "Dias en la aseguradora", "Comentarios", "Responsable", "Fecha Hoy",
            "22-jul-26",
        ]
        row = [
            "1", "Cliente", "RFC1", "123", "GMM", "Pam", "GMM", "Servicios",
            "Rehabilitación GMM", "Ingresado", "2026-07-01", "0", "20/07/2026",
            "0", "Nota", "Pam", "", "Seguimiento",
        ]
        parsed = parse_pending_workbook(
            workbook_bytes("Base", headers, [row]),
            source,
            today=date(2026, 7, 23),
        )
        summary = parsed["rows"][0]["summary"]
        self.assertEqual(summary["Días Transcurridos"], "22")
        self.assertEqual(summary["Dias en la aseguradora"], "3")
        self.assertEqual(summary["Comentarios"], "Nota")
        self.assertNotIn("Fecha Hoy", summary)
        self.assertEqual(parsed["rows"][0]["latest_update"]["update"], "Seguimiento")

    def test_siniestros_new_date_columns_are_derived(self):
        source = PendingSource("siniestros", "Test", "TEST_ID", "file", "Base", 12)
        headers = [
            "Folio Titán", "ASEGURADO", "RFC", "Tipo de Trámite", "Trámite",
            "Estatus", "Comentarios", "Notas Especiales",
            "Fecha de registro de siniestro", "Dias desde registro del siniestro",
            "Fecha de envío a la aseguradora", "DIAS CUMPLIDOS EN LA ASEGURADORA",
            "Responsable", "Semaforo", "22/07/2026",
        ]
        row = [
            "1", "Cliente", "RFC1", "Reembolso", "Complemento", "Ingresado",
            "", "", "2026-07-01", "0", "2026-07-20", "0", "Pam", "Verde", "",
        ]
        parsed = parse_pending_workbook(
            workbook_bytes("Base", headers, [row]),
            source,
            today=date(2026, 7, 23),
        )
        summary = parsed["rows"][0]["summary"]
        self.assertEqual(summary["Dias desde registro del siniestro"], "22")
        self.assertEqual(summary["DIAS CUMPLIDOS EN LA ASEGURADORA"], "3")

    def test_derived_days_are_blank_without_date_and_never_negative(self):
        self.assertEqual(
            _derived_day_values(
                {"Fecha Inicio": "", "Días Transcurridos": "99"},
                date(2026, 7, 23),
            ),
            {"Días Transcurridos": ""},
        )
        self.assertEqual(
            _derived_day_values(
                {"Fecha Inicio": "2026-07-25", "Días Transcurridos": ""},
                date(2026, 7, 23),
            ),
            {"Días Transcurridos": "0"},
        )

    def test_report_classifies_each_counter_and_excludes_already_submitted_records(self):
        emision = {
            "rows": [
                {
                    "source_row": 2,
                    "summary": {
                        "Asegurado": "Previo Verde",
                        "RFC": "RFC1",
                        "Días Transcurridos": "5",
                        "Dias en la aseguradora": "",
                    },
                    "latest_update": {"date": "22-jul-26", "update": "Preparando"},
                },
                {
                    "source_row": 3,
                    "summary": {
                        "Asegurado": "Previo Amarillo",
                        "RFC": "RFC2",
                        "Días Transcurridos": "6",
                        "Dias en la aseguradora": "",
                    },
                    "latest_update": {},
                },
                {
                    "source_row": 4,
                    "summary": {
                        "Asegurado": "En aseguradora Rojo",
                        "RFC": "RFC3",
                        "Días Transcurridos": "20",
                        "Dias en la aseguradora": "11",
                    },
                    "latest_update": {},
                },
                {
                    "source_row": 5,
                    "summary": {
                        "Asegurado": "Sin fecha",
                        "Días Transcurridos": "",
                        "Dias en la aseguradora": "",
                    },
                    "latest_update": {},
                },
            ],
        }
        siniestros = {
            "rows": [
                {
                    "source_row": 2,
                    "summary": {
                        "ASEGURADO": "Siniestro previo",
                        "Dias desde registro del siniestro": "10",
                        "DIAS CUMPLIDOS EN LA ASEGURADORA": "",
                    },
                    "latest_update": {},
                },
                {
                    "source_row": 3,
                    "summary": {
                        "ASEGURADO": "Siniestro aseguradora",
                        "Dias desde registro del siniestro": "12",
                        "DIAS CUMPLIDOS EN LA ASEGURADORA": "3",
                    },
                    "latest_update": {},
                },
            ],
        }

        report = build_pending_report(emision, siniestros, date(2026, 7, 23))
        emision_before, emision_inside = report["sections"][0]["metrics"]
        siniestro_before, siniestro_inside = report["sections"][1]["metrics"]

        self.assertEqual(emision_before["counts"], {"verde": 1, "amarillo": 1, "rojo": 0})
        self.assertEqual(emision_inside["counts"], {"verde": 0, "amarillo": 0, "rojo": 1})
        self.assertEqual(siniestro_before["counts"], {"verde": 0, "amarillo": 1, "rojo": 0})
        self.assertEqual(siniestro_inside["counts"], {"verde": 1, "amarillo": 0, "rojo": 0})

    def test_report_html_contains_summary_and_escapes_record_values(self):
        report = build_pending_report(
            {
                "rows": [{
                    "source_row": 2,
                    "summary": {
                        "Asegurado": "Cliente <Uno>",
                        "RFC": "RFC1",
                        "Solicitud de": "Rehabilitación GMM",
                        "Días Transcurridos": "3",
                        "Dias en la aseguradora": "",
                    },
                    "latest_update": {},
                }],
            },
            {"rows": []},
            date(2026, 7, 23),
        )
        html = pending_report_html(report)
        self.assertIn("Emisión y Servicios", html)
        self.assertIn("Verde (0-5)", html)
        self.assertIn("Cliente &lt;Uno&gt;", html)
        self.assertNotIn("Cliente <Uno>", html)

    def test_report_recipients_accept_multiple_separators_and_remove_duplicates(self):
        self.assertEqual(
            normalize_report_recipients([
                "Pamela.Alfaro@taiico.com; veronica.alfaro@taiico.com",
                "pamela.alfaro@taiico.com\nalberto.alfaro@taiico.com",
            ]),
            [
                "pamela.alfaro@taiico.com",
                "veronica.alfaro@taiico.com",
                "alberto.alfaro@taiico.com",
            ],
        )

    def test_report_recipients_reject_invalid_or_empty_values(self):
        with self.assertRaises(ValueError):
            normalize_report_recipients(["no-es-correo"])
        with self.assertRaises(ValueError):
            normalize_report_recipients(["", "  "])

    def test_document_requirements_follow_classification_and_request(self):
        gmm = requirements_for("GMM", "Reembolso GMM")
        vida = requirements_for("Vida", "Rescate total / parcial VIDA")
        self.assertIn("Informe medico", gmm)
        self.assertIn("Estado de cuenta", vida)
        self.assertEqual(requirements_for("GMM", "Solicitud desconocida"), [])
        self.assertEqual(set(GMM_DOCUMENT_REQUIREMENTS), GMM_REQUEST_OPTIONS)
        self.assertEqual(set(VIDA_DOCUMENT_REQUIREMENTS), VIDA_REQUEST_OPTIONS)

    def test_multiple_requests_combine_requirements_without_duplicates(self):
        selected = "Cambio de contratante GMM, Rehabilitación GMM & Cambio clave de agente"
        self.assertEqual(
            split_request_types(selected),
            [
                "Cambio de contratante GMM",
                "Rehabilitación GMM",
                "Cambio clave de agente",
            ],
        )
        documents = requirements_for("GMM", selected)
        self.assertEqual(documents.count("Solicitud de Cambios"), 1)
        self.assertIn("Cédula Fiscal", documents)
        self.assertIn("Formato de Rehabilitación", documents)
        self.assertIn("Carta Cliente", documents)


if __name__ == "__main__":
    unittest.main()
