import asyncio
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from services import metlife_collection_base as service
from services.cobranza import get_metlife_collection_base


@pytest.fixture
def base():
    service._read_base.cache_clear()
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'base.xlsx'
        path.write_bytes(b'first')
        payload = dict(policy_number='000123', paid_until_date=date(2026, 9, 15),
                       renewal_deadline=date(2027, 1, 1), agent_code='123',
                       premium_amount=12000, modal_premium_amount=1000)
        rows = [SimpleNamespace(normalized_payload=payload),
                SimpleNamespace(normalized_payload={**payload, 'policy_number': '000456', 'paid_until_date': None})]
        with (patch.dict(service.METLIFE_PATHS, RENOVACIONES_VIDA=str(path), RENOVACIONES_GMM=str(path)),
              patch.object(service, 'parse_metlife_vida_renewal_workbook', return_value=(rows, [])) as vida,
              patch.object(service, 'parse_metlife_gmm_renewal_workbook', return_value=(rows, [])) as gmm,
              patch.object(service, 'portal_collection_index', return_value={('000123', '2027-01-01'): {'paid_until': '2026-10-15', 'checked_at': '2026-09-14T12:00:00+00:00'}}),
              patch.object(service, 'promotoria_by_agent_key', return_value={'123': 'TAIICO'})):
            yield path, rows, vida, gmm
    service._read_base.cache_clear()


def admin():
    return SimpleNamespace(is_agent=False, is_central_admin=True)


@pytest.mark.parametrize('branch', ['VIDA', 'GMM'])
def test_base_without_payments_and_paid_until_filter(base, branch):
    rows = asyncio.run(get_metlife_collection_base(branch, '2026-09-15', '2026-09-15', admin()))
    assert len(rows) == 1
    assert rows[0]['# de Póliza'] == '000123'
    assert rows[0]['Pagado Hasta'] == '2026-09-15'
    assert rows[0]['Fin Vigencia'] == '2027-01-01'
    if branch == 'GMM':
        assert rows[0]['Pagado Hasta (base)'] == '2026-09-15'
        assert rows[0]['Pagado Hasta (portal)'] == '2026-10-15'
        assert rows[0]['Última consulta al portal'] == '2026-09-14 12:00'
    assert len(service.collection_base(branch, None, None, admin())) == 2
    assert service.collection_base(branch, None, '2026-09-14', admin()) == []
    assert service.collection_base(branch, '2026-09-16', None, admin()) == []
    assert (base[2] if branch == 'VIDA' else base[3]).call_count == 1
    assert (base[3] if branch == 'VIDA' else base[2]).call_count == 0


def test_new_upload_invalidates_cache(base):
    path, rows, parser, _ = base
    service.collection_base('VIDA', None, None, admin())
    path.write_bytes(b'new upload version')
    service.collection_base('VIDA', None, None, admin())
    assert parser.call_count == 2


def test_promotoria_scope(base):
    profile = SimpleNamespace(is_agent=False, is_central_admin=False, promotorias=('OTHER',))
    assert service.collection_base('VIDA', None, None, profile) == []
    profile.promotorias = ('TAIICO',)
    assert len(service.collection_base('VIDA', None, None, profile)) == 2


def test_agent_scope(base):
    profile = SimpleNamespace(is_agent=True)
    with (patch.object(service, 'profile_allows_insurer', return_value=True),
          patch.object(service, 'profile_allows_agent_key', return_value=False)):
        assert service.collection_base('GMM', None, None, profile) == []
    with patch.object(service, 'profile_allows_insurer', return_value=False):
        assert service.collection_base('GMM', None, None, profile) == []


@pytest.mark.parametrize('start,end', [('bad', None), ('2026-10-01', '2026-09-01')])
def test_invalid_dates(base, start, end):
    with pytest.raises(HTTPException) as error:
        service.collection_base('VIDA', start, end, admin())
    assert error.value.status_code == 422


def test_missing_base(base):
    base[0].unlink()
    with pytest.raises(HTTPException) as error:
        service.collection_base('VIDA', None, None, admin())
    assert error.value.status_code == 404
