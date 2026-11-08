"""Bounded extraction and hash-pinned, partial official form preparation."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black, white
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'assets/metlife_forms/medicalife-familiar-ig-1-002-v27.pdf'
TEMPLATE_SHA = 'efc99565e1b842a1c7d77890e30c9a0d590b53107d476a087920d03d239e4eab'
SOURCE_URL = 'https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/recas/Seguros-Individuales/Seguros-de-Gastos-Medicos-y-Accidentes-MedicaLife-Familiar/ig-1-002-ver25-validacion.pdf'
CATALOG_URL = 'https://www.metlife.com.mx/bin/MLApp/globalMarketingPlatform/fetchFormsLibrary'
CATALOG_PARAMS = {'products': 'Seguros-de-Gastos-Medicos-y-Accidentes-MedicaLife-Familiar',
                  'formsPath': '/content/dam/metlifecom/mx/pdfs/recas/Seguros-Individuales'}
FORM_FIELDS = {'paternal_surname': 'Apellido paterno', 'maternal_surname': 'Apellido materno',
               'given_names': 'Nombre(s)', 'curp': 'CURP', 'email': 'Correo electrónico', 'phone': 'Teléfono'}
MAX_READ = 4 * 1024 * 1024


def status_path():
    return Path(os.getenv('MESA_FORMS_STATE_PATH', str(ROOT.parent / '.runtime/mesa-form-status.json')))


def form_status():
    try:
        state = json.loads(status_path().read_text())
    except (OSError, ValueError):
        state = {'status': 'not_checked', 'notice': 'Todavía no se ha comprobado la fuente oficial.'}
    checked = state.get('checked_at', '')
    try:
        stale = (datetime.now(timezone.utc) - datetime.fromisoformat(checked)).total_seconds() > 7 * 86400
    except ValueError:
        stale = True
    return {**state, 'stale': stale, 'version': 'IG-1-002 VER. 27', 'sha256': TEMPLATE_SHA,
            'source_url': SOURCE_URL, 'fields': FORM_FIELDS,
            'can_generate': state.get('status') == 'verified' and not stale}


def _bounded_get(client, url, **kwargs):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'www.metlife.com.mx':
        raise ValueError('untrusted official URL')
    with client.stream('GET', url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes(65536):
            content.extend(chunk)
            if len(content) > MAX_READ:
                raise ValueError('official resource too large')
        return bytes(content)


def check_official_form():
    """Daily read-only fetch. Changed templates are NEVER activated automatically."""
    state = {'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            catalog = json.loads(_bounded_get(client, CATALOG_URL, params=CATALOG_PARAMS))
            docs = catalog.get('response', {}).get('docs', [])
            candidates = [d for d in docs if 'solicitud de seguro de gastos' in d.get('file_title', '').casefold()]
            expected_path = urlparse(SOURCE_URL).path
            if len(candidates) != 1 or candidates[0].get('file_url') != expected_path:
                state.update(status='changed', notice='Cambió la solicitud publicada en el catálogo oficial. Revisa el formato y su mapeo antes de generar.')
            else:
                content = _bounded_get(client, SOURCE_URL)
                digest = hashlib.sha256(content).hexdigest()
                state['observed_sha256'] = digest
                state.update(status='verified' if digest == TEMPLATE_SHA else 'changed',
                             notice='Fuente oficial verificada.' if digest == TEMPLATE_SHA else 'El PDF oficial cambió. Se bloqueó el llenado hasta verificar el nuevo formato.')
    except Exception:
        state.update(status='unavailable', notice='No se pudo verificar la fuente oficial. No se activaron versiones nuevas.')
    path = status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False))
    temporary.replace(path)
    return state


def extract_candidates(content):
    if len(content) > MAX_READ:
        raise HTTPException(413, 'La lectura admite PDF de hasta 4 MB.')
    if not content.startswith(b'%PDF-'):
        raise HTTPException(422, 'La extracción actual requiere un PDF con texto. Las imágenes o escaneos necesitan captura manual.')
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError('encrypted')
        if len(reader.pages) > 30:
            raise HTTPException(422, 'La lectura admite hasta 30 páginas. Divide el documento.')
        patterns = {
            'rfc': r'(?<![A-Z0-9Ñ&])[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}(?![A-Z0-9])',
            'curp': r'(?<![A-Z0-9])[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d(?![A-Z0-9])',
            'email': r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}',
            'phone': r'(?<!\d)(?:\+52[ -]?)?(?:\d{2,3}[ -])?\d{3,4}[ -]\d{4}(?!\d)',
        }
        candidates, seen = [], set()
        total = 0
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ''
            total += len(text)
            if total > 100000:
                raise HTTPException(422, 'El documento contiene demasiado texto para esta lectura. Divide el archivo.')
            for field, pattern in patterns.items():
                for match in re.finditer(pattern, text, flags=re.I):
                    value = match.group().strip()
                    if field in {'rfc', 'curp'}:
                        value = value.upper()
                    if field == 'rfc' and value in {'XAXX010101000', 'XEXX010101000'}:
                        continue
                    key = (field, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append({'field': field, 'value': value, 'page': number,
                        'excerpt': text[max(0, match.start()-65):match.end()+65].strip()})
                    if len(candidates) >= 40:
                        return {'candidates': candidates, 'partial': True, 'notice': 'Mostrando hasta 40 coincidencias. Confirma a quién corresponde cada dato.'}
        return {'candidates': candidates, 'partial': False,
                'notice': 'Coincidencias del documento, no atribuidas automáticamente al contratante. Revisa la evidencia antes de confirmar.' if candidates else 'No se encontraron datos reconocibles en el texto. Puede requerir OCR o captura manual; no se leyó visualmente.'}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'No se pudo leer el PDF. Puede estar protegido o dañado.') from None


def generate_form(data, case_id, revision):
    state = form_status()
    if not state['can_generate']:
        raise HTTPException(409, state['notice'] + (' La comprobación está vencida.' if state['stale'] else ''))
    if data.get('product', '').strip().casefold() not in {'medicalife familiar', 'médicalife familiar'}:
        raise HTTPException(422, 'Este formato corresponde exclusivamente a MédicaLife Familiar. Confirma el producto de la cotización.')
    if not data.get('given_names') or not data.get('paternal_surname') or not data.get('rfc'):
        raise HTTPException(422, 'Confirma nombres, apellido paterno y RFC antes de generar el borrador.')
    source = TEMPLATE.read_bytes()
    if hashlib.sha256(source).hexdigest() != TEMPLATE_SHA:
        raise HTTPException(409, 'El formato local no coincide con la versión validada.')
    source_reader = PdfReader(io.BytesIO(source))
    if source_reader.get_fields() or any(a.get_object().get('/Subtype') == '/Widget' for p in source_reader.pages for a in p.get('/Annots', [])):
        raise HTTPException(409, 'El formato tiene campos no previstos por este mapeo.')
    overlay = io.BytesIO()
    canvas = Canvas(overlay, pagesize=(612, 792))
    expected = {}
    def field(name, value, x, y, width, size=10, height=14):
        if not value:
            return
        if stringWidth(value, 'Helvetica', size) > width - 4:
            raise HTTPException(422, 'El dato de ' + name + ' no cabe en el formato. Acórtalo solo si corresponde o complétalo manualmente.')
        if any(ord(c) > 255 for c in value):
            raise HTTPException(422, 'El formato requiere revisión manual para caracteres especiales.')
        canvas.acroForm.textfield(name=name, value=value, x=x, y=y, width=width, height=height,
            fontName='Helvetica', fontSize=size, borderWidth=0, fillColor=white, textColor=black,
            forceBorder=False, maxlen=max(100, len(value)))
        expected[name] = value
    field('Apellido paterno', data.get('paternal_surname', ''), 25, 584, 180)
    field('Apellido materno', data.get('maternal_surname', ''), 218, 584, 176)
    field('Nombres', data.get('given_names', ''), 405, 584, 182)
    # Character boxes are mapped from the verified first page, not inferred at runtime.
    for key, start, step, y in [('curp', 24.5, 14.63, 437), ('rfc', 316.2, 14.83, 437)]:
        for index, letter in enumerate(data.get(key, '')):
            x = start + index * step + (7.4 if key == 'rfc' and index >= 10 else 0)
            field(f'{key}_{index+1}', letter, x + 2, y - 1, step - 3, 9, height=10)
    email = data.get('email', '')
    if email:
        local, domain = email.rsplit('@', 1)
        field('Correo usuario', local, 25, 401, 164, 9)
        field('Correo dominio', domain, 207, 401, 150, 9)
    field('Telefono', data.get('phone', ''), 367, 401, 175, 10)
    canvas.showPage(); canvas.save()
    writer = PdfWriter()
    writer.clone_document_from_reader(source_reader)
    overlay_reader = PdfReader(io.BytesIO(overlay.getvalue()))
    writer.pages[0].merge_page(overlay_reader.pages[0])
    # merge_page preserves widgets; attach them to one canonical AcroForm tree.
    writer.reattach_fields()
    from pypdf.generic import NameObject
    writer.root_object['/AcroForm'][NameObject('/DR')] = overlay_reader.trailer['/Root']['/AcroForm']['/DR'].clone(writer)
    writer.update_page_form_field_values(None, expected, auto_regenerate=False)
    for page in writer.pages:
        stamp = io.BytesIO(); c = Canvas(stamp, pagesize=(612, 792))
        c.setFillColorRGB(.65, .10, .10); c.setFont('Helvetica', 7)
        c.drawString(17, 780, f'BORRADOR PARCIAL - REQUIERE REVISION Y DATOS RESTANTES | Mesa {case_id[:8]} v{revision}')
        c.showPage(); c.save()
        page.merge_page(PdfReader(io.BytesIO(stamp.getvalue())).pages[0])
    output = io.BytesIO(); writer.write(output)
    result = output.getvalue()
    verify = PdfReader(io.BytesIO(result)).get_fields() or {}
    if any(verify.get(k, {}).get('/V') != v for k, v in expected.items()):
        raise HTTPException(500, 'No se pudo verificar el llenado del borrador.')
    return result, {'source_url': SOURCE_URL, 'template_sha256': TEMPLATE_SHA, 'version': state['version'],
                    'case_revision': revision, 'fields': expected, 'partial': True}
