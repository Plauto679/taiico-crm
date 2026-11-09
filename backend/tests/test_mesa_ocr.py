import io
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from services import mesa_ocr, mesa_documents as forms


def test_worker_unavailable_is_explicit(monkeypatch):
    monkeypatch.setattr(mesa_ocr, 'available', lambda: False)
    with pytest.raises(HTTPException) as error:
        mesa_ocr.read_pages(b'scan')
    assert error.value.status_code == 503


def test_worker_timeout_cleans_temporary_document(monkeypatch):
    monkeypatch.setattr(mesa_ocr, 'available', lambda: True)
    paths = []
    def run(args, **kwargs):
        paths.append(Path(args[1]))
        assert paths[-1].read_bytes() == b'scan'
        assert kwargs['timeout'] == 90 and 'shell' not in kwargs
        raise subprocess.TimeoutExpired(args, 90)
    monkeypatch.setattr(mesa_ocr.subprocess, 'run', run)
    with pytest.raises(HTTPException) as error:
        mesa_ocr.read_pages(b'scan')
    assert error.value.status_code == 504
    assert not paths[0].exists()


def test_mixed_pdf_covers_scanned_pages_and_marks_ocr(monkeypatch):
    image = Image.new('RGB', (300, 200), 'white')
    stream = io.BytesIO(); c = Canvas(stream)
    c.drawString(40, 700, 'Correo: first@example.com'); c.showPage()
    c.drawImage(ImageReader(image), 40, 400, 300, 200); c.save()
    monkeypatch.setattr(mesa_ocr, 'read_pages', lambda content: [
        {'page': 1, 'text': 'Correo first@example.com', 'method': 'ocr', 'lines': []},
        {'page': 2, 'text': 'RFC: AAAA901001AB1\nApellido paterno: PRUEBA\nNombres: ANA MARIA', 'method': 'ocr', 'lines': []}])
    result = forms.extract_candidates(stream.getvalue())
    assert result['used_ocr']
    assert result['pages'][0]['method'] == 'text'
    assert next(v for v in result['candidates'] if v['field'] == 'rfc')['page'] == 2
    assert next(v for v in result['candidates'] if v['field'] == 'given_names')['value'] == 'ANA MARIA'


def test_ocr_does_not_guess_identifiers_or_split_full_names(monkeypatch):
    monkeypatch.setattr(mesa_ocr, 'read_pages', lambda content: [{'page': 1,
        'text': 'Nombre completo: Ana Prueba Ejemplo\nRFC: AAAA9O1001AB1', 'method': 'ocr', 'lines': []}])
    result = forms.extract_candidates(b'\x89PNG\r\n\x1a\nplaceholder')
    assert not result['candidates']
    assert 'AAAA9O1001AB1' in result['pages'][0]['text']


def test_guidance_does_not_claim_whole_form_complete():
    data = {'product': 'MédicaLife Familiar', 'paternal_surname': 'Prueba', 'given_names': 'Ana',
            'rfc': 'AAAA901001AB1', 'maternal_surname_not_applicable': True}
    progress = forms.form_progress(data)
    assert progress['ready_for_partial_draft']
    assert 'maternal_surname' not in [f['key'] for f in progress['pending_fields']]
    assert progress['manual_sections'] and progress['filled_count'] < progress['mapped_count']
    assert not forms.form_progress({'product': 'Primordial'})['supported']


@pytest.mark.skipif(not mesa_ocr.available(), reason='Local macOS OCR worker not installed')
def test_real_local_ocr_on_scan():
    font_path = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
    if not font_path.exists(): pytest.skip('macOS font unavailable')
    image = Image.new('RGB', (1500, 600), 'white')
    draw = ImageDraw.Draw(image); font = ImageFont.truetype(str(font_path), 40)
    draw.text((60, 80), 'RFC: AAAA901001AB1', font=font, fill='black')
    draw.text((60, 180), 'Nombres: ANA MARIA', font=font, fill='black')
    stream = io.BytesIO(); image.save(stream, format='PNG')
    result = forms.extract_candidates(stream.getvalue())
    assert any(v['value'] == 'AAAA901001AB1' for v in result['candidates'])
    assert any(v['field'] == 'given_names' and v['value'] == 'ANA MARIA' for v in result['candidates'])
