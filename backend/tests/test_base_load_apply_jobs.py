import asyncio
import json
from unittest.mock import patch

from fastapi import BackgroundTasks
from services import base_loads as service


def test_apply_is_background_and_retries_return_receipt_without_writing_again(tmp_path):
    token = 'a' * 32
    directory = tmp_path / token
    directory.mkdir()
    for name in ('source.xlsx', 'prepared.xlsx', 'agents.xlsx'):
        (directory / name).write_bytes(b'workbook')
    manifest = {'source_key': 'renovaciones.metlife_gmm', 'sha256': service.file_sha256(directory / 'source.xlsx'),
                'candidate_sha256': 'candidate', 'canonical_sha256': 'canonical', 'filename': 'test.xlsx',
                'preview': {'final_row_count': 13291}}
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    with (patch.object(service, 'staging_root', return_value=tmp_path),
          patch.object(service, 'apply_prepared_workbook', return_value={'backup_file_id': 'backup'}) as apply,
          patch('services.renewal_ingestion.sync_local_canonical_renewals', return_value={'status': 'completed'})):
        tasks = BackgroundTasks()
        response = asyncio.run(service.apply_metlife_gmm_base(token, tasks, True))
        assert response.status_code == 202
        apply.assert_not_called()
        duplicate_tasks = BackgroundTasks()
        assert asyncio.run(service.apply_metlife_gmm_base(token, duplicate_tasks, True)).status_code == 202
        assert duplicate_tasks.tasks == []
        asyncio.run(tasks())
        status = asyncio.run(service.get_gmm_apply_status(token))
        assert status['status'] == 'completed'
        assert status['result']['backup_file_id'] == 'backup'
        assert not (directory / 'source.xlsx').exists()
        assert asyncio.run(service.apply_metlife_gmm_base(token, BackgroundTasks(), True)) == status['result']
        service.cleanup_expired_previews()
        assert (directory / 'apply-result.json').exists()
        apply.assert_called_once()


def test_failed_apply_is_not_repeated_automatically(tmp_path):
    directory = tmp_path / ('a' * 32)
    directory.mkdir()
    (directory / 'source.xlsx').write_bytes(b'workbook')
    manifest = {'sha256': service.file_sha256(directory / 'source.xlsx'), 'candidate_sha256': 'candidate', 'canonical_sha256': 'canonical'}
    with (patch.object(service, 'staging_root', return_value=tmp_path),
          patch.object(service, 'apply_prepared_workbook', side_effect=RuntimeError('Drive no disponible')) as apply):
        result = service.run_gmm_apply_job(directory, manifest)
        assert result == {'status': 'failed', 'detail': 'Drive no disponible'}
        tasks = BackgroundTasks()
        response = asyncio.run(service.apply_metlife_gmm_base(directory.name, tasks, True))
        assert json.loads(response.body)['status'] == 'failed'
        assert tasks.tasks == []
        apply.assert_called_once()


def test_no_agent_matches_rejects_apply_without_backup_or_job(tmp_path):
    import pytest
    from fastapi import HTTPException

    token = 'b' * 32
    directory = tmp_path / token
    directory.mkdir()
    for name in ('source.xlsx', 'prepared.xlsx'):
        (directory / name).write_bytes(b'workbook')
    for product in ('gmm', 'vida'):
        (directory / 'manifest.json').write_text(json.dumps({
            'source_key': f'renovaciones.metlife_{product}',
            'preview': {'rows_after_agent_filter': 0},
        }))
        tasks = BackgroundTasks()
        with (patch.object(service, 'staging_root', return_value=tmp_path),
              patch.object(service, 'apply_prepared_workbook') as apply):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(service.apply_metlife_gmm_base(token, tasks, True)
                            if product == 'gmm' else service.apply_metlife_vida_base(token))
            assert exc.value.status_code == 409
            assert 'No hay claves de agente con coincidencias' in exc.value.detail
            assert tasks.tasks == []
            assert not (directory / 'apply-claim').exists()
            apply.assert_not_called()


def test_latest_loads_only_applied_per_product_and_survive_cleanup(tmp_path):
    from datetime import datetime, timezone
    import os

    for token, product, filename, applied_at, applied in (
        ('a', 'gmm', 'anterior.xlsx', '2026-11-01T10:00:00+00:00', True),
        ('b', 'gmm', 'reciente.xlsx', '2026-11-02T10:00:00+00:00', True),
        ('c', 'vida', 'vida.xlsx', '2026-11-01T10:00:00+00:00', True),
        ('d', 'gmm', 'solo-preview.xlsx', '2026-11-03T10:00:00+00:00', False),
    ):
        directory = tmp_path / (token * 32)
        directory.mkdir()
        (directory / 'manifest.json').write_text(json.dumps({'source_key': f'renovaciones.metlife_{product}'}))
        if applied:
            (directory / 'apply-result.json').write_text(json.dumps({'applied': True, 'filename': filename, 'applied_at': applied_at}))
        old = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        os.utime(directory, (old, old))
    with patch.object(service, 'staging_root', return_value=tmp_path):
        service.cleanup_expired_previews()
        result = service.latest_base_loads()
        assert result['gmm']['filename'] == 'reciente.xlsx'
        assert result['vida']['filename'] == 'vida.xlsx'
