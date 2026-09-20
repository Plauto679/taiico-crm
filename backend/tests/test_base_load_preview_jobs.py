import asyncio
import json
import os
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from services import base_loads as service


@pytest.fixture
def staging(tmp_path):
    with patch.object(service, 'staging_root', return_value=tmp_path):
        yield tmp_path


def test_upload_returns_job_before_work_and_polls_completed_manifest(staging):
    tasks = BackgroundTasks()
    with patch.object(service, 'prepare_gmm_preview') as prepare:
        response = asyncio.run(service.preview_metlife_gmm_base(tasks, UploadFile(BytesIO(b'xlsx'), filename='report.xlsx'), True))
        assert response.status_code == 202
        prepare.assert_not_called()
        token = json.loads(response.body)['token']
        assert asyncio.run(service.get_gmm_preview_status(token)) == {'status': 'processing'}
        def finish(directory, *_args):
            result = {'token': token, 'source_key': 'renovaciones.metlife_gmm', 'preview': {'source_rows': 223741}}
            (directory / 'manifest.json').write_text(json.dumps(result))
            return result
        prepare.side_effect = finish
        asyncio.run(tasks())
    progress = asyncio.run(service.get_gmm_preview_status(token))
    assert progress['status'] == 'completed'
    assert progress['result']['preview']['source_rows'] == 223741


def test_failed_job_and_interrupted_job_are_reported(staging):
    directory = staging / ('a' * 32)
    directory.mkdir()
    with patch.object(service, 'prepare_gmm_preview', side_effect=ValueError('Columnas incorrectas')):
        service.run_gmm_preview_job(directory, 'report.xlsx', 0, 'hash')
    assert asyncio.run(service.get_gmm_preview_status(directory.name)) == {'status': 'failed', 'detail': 'Columnas incorrectas'}
    service.write_preview_status(directory, {'status': 'processing', 'worker_pid': os.getpid() + 1})
    assert asyncio.run(service.get_gmm_preview_status(directory.name))['status'] == 'failed'


def test_status_rejects_invalid_or_missing_token(staging):
    for token, code in [('../outside', 400), ('a' * 32, 404)]:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.get_gmm_preview_status(token))
        assert error.value.status_code == code
