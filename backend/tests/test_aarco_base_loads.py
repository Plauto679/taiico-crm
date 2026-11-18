from datetime import date
from unittest.mock import patch
from openpyxl import Workbook
from services import aarco_base_loads as svc


def workbook(path, headers, rows):
    w=Workbook();s=w.active;s.append(headers)
    for row in rows:s.append(row)
    w.save(path)


def test_monthly_omission_preserves_internal_fields_and_periods(tmp_path):
    headers=['AGENTE','ASEGURADORA','POLIZA','CONTRATANTE','INICIO VIGENCIA','PRIMA NETA ANUAL']
    canonical=tmp_path/'canonical.xlsx'; incoming=tmp_path/'monthly.xlsx'; out=tmp_path/'out.xlsx'
    workbook(canonical,headers+['FIN VIGENCIA','Email','EXPEDIENTE','ESTATUS_DE_RENOVACION'],[
        ['A','AXA','001','Cliente',date(2025,1,1),10,date(2026,1,1),'a@example.com','https://drive.google.com/folder','En proceso'],
        ['A','AXA','001','Cliente',date(2024,1,1),9,date(2025,1,1),None,None,None]])
    workbook(incoming,list(reversed(headers)),[list(reversed(['A','AXA','001','Cliente',date(2025,1,1),20]))])
    with patch.dict(svc.AARCO_PATHS,RENOVACIONES=canonical):
        preview=svc.prepare(incoming,out)
    _,rows=svc.read_rows(out)
    assert len(rows)==2
    current=rows['001','2025-01-01']
    assert current['PRIMA NETA ANUAL']==20
    assert current['Email']=='a@example.com'
    assert current['ESTATUS_DE_RENOVACION']=='En proceso'
    assert preview['final_policy_count']==1


def test_annual_end_leap_day():
    assert svc.annual_end(date(2024,2,29))==date(2025,2,28)


def test_missing_required_header_rejected(tmp_path):
    import pytest
    p=tmp_path/'bad.xlsx';workbook(p,['POLIZA'],[['001']])
    with pytest.raises(ValueError,match='Faltan columnas'):svc.read_rows(p)


def test_source_currency_formats():
    assert svc.money('$10.115,28')==svc.Decimal('10115.28')
    assert svc.money('$10,115.28')==svc.Decimal('10115.28')
