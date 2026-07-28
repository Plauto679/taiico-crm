from __future__ import annotations

import io
import re
import unittest
import zipfile
from xml.etree import ElementTree

from services.xlsx_integrity import repair_workbook_integrity


class XlsxIntegrityTests(unittest.TestCase):
    def test_repairs_stale_row_spans_and_missing_table_uids(self):
        workbook = io.BytesIO()
        with zipfile.ZipFile(workbook, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                (
                    '<Types><Override PartName="/xl/calcChain.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.calcChain+xml"/></Types>'
                ),
            )
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                (
                    '<Relationships><Relationship Id="rId9" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/calcChain" Target="calcChain.xml"/></Relationships>'
                ),
            )
            archive.writestr(
                "xl/workbook.xml",
                '<workbook><calcPr calcId="123"/></workbook>',
            )
            archive.writestr("xl/calcChain.xml", '<calcChain><c r="B2"/></calcChain>')
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                (
                    '<worksheet><sheetData>'
                    '<row r="1" spans="1:2"><c r="A1"/><c r="D1"/></row>'
                    '<row r="2"><c r="C2"/></row>'
                    '</sheetData></worksheet>'
                ),
            )
            archive.writestr(
                "xl/tables/table1.xml",
                (
                    '<table xmlns:xr3="http://schemas.microsoft.com/office/'
                    'spreadsheetml/2016/revision3"><tableColumns count="2">'
                    '<tableColumn id="1" xr3:uid="{EXISTING}" name="Uno"/>'
                    '<tableColumn id="2" name="Dos"/>'
                    '</tableColumns></table>'
                ),
            )
            archive.writestr("unchanged.bin", b"preserve-me")

        repaired = repair_workbook_integrity(workbook.getvalue())
        with zipfile.ZipFile(io.BytesIO(repaired)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
            table = archive.read("xl/tables/table1.xml").decode()
            self.assertEqual(archive.read("unchanged.bin"), b"preserve-me")
            self.assertNotIn("xl/calcChain.xml", archive.namelist())
            self.assertNotIn(
                "calcChain",
                archive.read("[Content_Types].xml").decode(),
            )
            self.assertNotIn(
                "calcChain",
                archive.read("xl/_rels/workbook.xml.rels").decode(),
            )
            workbook_xml = archive.read("xl/workbook.xml").decode()

        self.assertIn('<row r="1" spans="1:4">', sheet)
        self.assertIn('<row r="2" spans="3:3">', sheet)
        self.assertIn('xr3:uid="{EXISTING}"', table)
        generated = re.search(r'<tableColumn id="2" name="Dos" xr3:uid="\{([^}]+)\}"/>', table)
        self.assertIsNotNone(generated)
        ElementTree.fromstring(table)
        self.assertIn('calcMode="auto"', workbook_xml)
        self.assertIn('fullCalcOnLoad="1"', workbook_xml)
        self.assertIn('forceFullCalc="1"', workbook_xml)


if __name__ == "__main__":
    unittest.main()
