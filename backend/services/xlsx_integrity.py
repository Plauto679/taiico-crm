from __future__ import annotations

import io
import re
import uuid
import zipfile


def normalize_sheet_row_spans(sheet_xml: str) -> str:
    """Keep each row's optimization span aligned with its actual cells."""

    row_pattern = re.compile(r"<row\b[^>]*(?:/>|>.*?</row>)", re.DOTALL)

    def normalize_row(match: re.Match[str]) -> str:
        row_xml = match.group(0)
        columns = [
            column_number(letters)
            for letters in re.findall(r'<c\b[^>]*\br="([A-Z]+)\d+"', row_xml)
        ]
        if not columns:
            return row_xml
        span = f'{min(columns)}:{max(columns)}'
        if re.search(r'\bspans="[^"]*"', row_xml):
            return re.sub(r'\bspans="[^"]*"', f'spans="{span}"', row_xml, count=1)
        tag_end = row_xml.find(">")
        if tag_end < 0:
            tag_end = row_xml.find("/>")
        return row_xml[:tag_end] + f' spans="{span}"' + row_xml[tag_end:]

    return row_pattern.sub(normalize_row, sheet_xml)


def ensure_table_column_uids(table_xml: str) -> str:
    """Add revision identifiers when the workbook already uses Excel revision3."""

    if "xmlns:xr3=" not in table_xml:
        return table_xml

    tag_pattern = re.compile(r"<tableColumn\b[^>]*>")

    def add_uid(match: re.Match[str]) -> str:
        tag = match.group(0)
        if "xr3:uid=" in tag:
            return tag
        uid = str(uuid.uuid4()).upper()
        if tag.endswith("/>"):
            return tag[:-2] + f' xr3:uid="{{{uid}}}"/>'
        return tag[:-1] + f' xr3:uid="{{{uid}}}">'

    return tag_pattern.sub(add_uid, table_xml)


def repair_workbook_integrity(workbook: bytes) -> bytes:
    """Repair the narrow XLSX invariants used by Taiico's package-level writer."""

    with zipfile.ZipFile(io.BytesIO(workbook), "r") as source:
        has_calc_chain = "xl/calcChain.xml" in source.namelist()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as destination:
            for item in source.infolist():
                if item.filename == "xl/calcChain.xml":
                    # Cell insertion invalidates chain coordinates. Excel safely rebuilds it.
                    continue
                content = source.read(item.filename)
                if has_calc_chain and item.filename == "[Content_Types].xml":
                    content = _remove_calc_chain_content_type(content.decode("utf-8")).encode("utf-8")
                elif has_calc_chain and item.filename == "xl/_rels/workbook.xml.rels":
                    content = _remove_calc_chain_relationship(content.decode("utf-8")).encode("utf-8")
                elif has_calc_chain and item.filename == "xl/workbook.xml":
                    content = _request_full_recalculation(content.decode("utf-8")).encode("utf-8")
                elif item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    content = normalize_sheet_row_spans(content.decode("utf-8")).encode("utf-8")
                elif item.filename.startswith("xl/tables/") and item.filename.endswith(".xml"):
                    content = ensure_table_column_uids(content.decode("utf-8")).encode("utf-8")
                destination.writestr(item, content)
    return output.getvalue()


def column_number(letters: str) -> int:
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - 64
    return value


def _remove_calc_chain_content_type(xml: str) -> str:
    return re.sub(
        r'<Override\b(?=[^>]*\bPartName="/xl/calcChain\.xml")[^>]*/>',
        "",
        xml,
    )


def _remove_calc_chain_relationship(xml: str) -> str:
    relationship = re.compile(r"<Relationship\b[^>]*/>")

    def keep_unless_calc_chain(match: re.Match[str]) -> str:
        tag = match.group(0)
        return "" if "/calcChain" in tag or 'Target="calcChain.xml"' in tag else tag

    return relationship.sub(keep_unless_calc_chain, xml)


def _request_full_recalculation(xml: str) -> str:
    match = re.search(r"<calcPr\b[^>]*/>", xml)
    if match:
        tag = match.group(0)
        for name, value in (
            ("calcMode", "auto"),
            ("fullCalcOnLoad", "1"),
            ("forceFullCalc", "1"),
        ):
            if re.search(rf'\b{name}="[^"]*"', tag):
                tag = re.sub(rf'\b{name}="[^"]*"', f'{name}="{value}"', tag, count=1)
            else:
                tag = tag[:-2] + f' {name}="{value}"/>'
        return xml[:match.start()] + tag + xml[match.end():]

    calc_pr = '<calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>'
    insertion = xml.find("<extLst")
    if insertion < 0:
        insertion = xml.rfind("</workbook>")
    return xml[:insertion] + calc_pr + xml[insertion:]
