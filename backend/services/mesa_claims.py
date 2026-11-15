"""Reimbursement intake rules. Clinical statements and signatures stay with their authors."""
from __future__ import annotations

import calendar
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from services import mesa_hospital as hospital
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, ArrayObject, FloatObject, TextStringObject
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

ASSETS = Path(__file__).resolve().parents[1] / 'assets/metlife_forms'
SOURCE_PAGE = 'https://www.metlife.com.mx/tramites-y-servicios/tramites-de-seguros-de-gastos-medicos/reembolso/'
CLAIM_URL = 'https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/common-files/reclamacion-gmm/solicitud-de-reclamacion-gastos-medicos-mayores-vg-2-068-ver-12-pdf-editable.pdf'
MEDICAL_URL = 'https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/internas/Soy-Cliente/Tramites-y-Servicios/Programar-Cirugia/Informe-medico.pdf'
FORMS = {
    'claim': {'file': 'reclamacion-gmm-vg-2-068-v12.pdf', 'source_url': CLAIM_URL,
              'sha256': 'f7d41d38c376b80376c872f74c024f83221c68d1e85511b75659572fb15056b2', 'version': 'VG-2-068 VER. 12'},
    'medical': {'file': 'informe-medico-cc-1-020-v7.pdf', 'source_url': MEDICAL_URL,
                'sha256': '7f5efd22a6b8c6fc5b2779e885caa49622f9469fe3fce72f211d135022d7b792', 'version': 'CC-1-020 VER. 7'},
}
REVIEW_CHECKS = {
    'identity': 'Titular, paciente, póliza y siniestro contrastados con los documentos',
    'medical': 'Informes de todos los médicos completos, fechados y firmados; omisiones resueltas con el médico',
    'invoices': 'Cada factura PDF tiene su XML; RFC, conceptos, importes y total revisados',
    'conditions': 'Condiciones, vigencias y documentos adicionales del caso revisados; contrastar discrepancias del portal y PDF',
    'signature': 'Solicitud completa, declaraciones revisadas y firma del titular; no es solo el borrador parcial',
}


class ClaimFields(BaseModel):
    workflow: Literal['emision_gmm', 'reembolso_gmm', 'cirugia_programada_gmm', 'pago_directo_gmm'] = 'emision_gmm'
    hospital_name: str = Field(default='', max_length=180)
    event_date: str = Field(default='', max_length=10)
    admission_date: str = Field(default='', max_length=10)
    hospital_phase: Literal['', 'admission', 'stay', 'discharge'] = ''
    hospital_in_network: bool | None = None
    doctors_in_network: bool | None = None
    doctors_accept_tariff: bool | None = None
    policy_current_paid: bool | None = None
    has_surgery_pass: bool | None = None
    hospital_reported: bool | None = None
    stay_over_24h: bool | None = None
    mp_required: bool | None = None
    claim_stage: Literal['', 'initial', 'complement'] = ''
    policy_number: str = Field(default='', max_length=40)
    contractor_name: str = Field(default='', max_length=150)
    claim_number: str = Field(default='', max_length=40)
    responding_request: bool | None = None
    previous_dcn: str = Field(default='', max_length=50)
    patient_paternal_surname: str = Field(default='', max_length=60)
    patient_maternal_surname: str = Field(default='', max_length=60)
    patient_given_names: str = Field(default='', max_length=80)
    patient_curp: str = Field(default='', max_length=18)
    patient_minor: bool | None = None
    patient_has_curp: bool | None = None
    bank_changed: bool | None = None
    includes_medicines: bool | None = None
    includes_studies: bool | None = None
    includes_histopathology: bool | None = None
    invoices_itemized: bool | None = None
    bank_holder_complete: bool | None = None
    digital_signature: bool | None = None
    medical_report_date: str = Field(default='', max_length=10)
    bank_statement_date: str = Field(default='', max_length=10)
    address_proof_date: str = Field(default='', max_length=10)

    @field_validator('*', mode='before')
    @classmethod
    def trim_claim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('medical_report_date', 'bank_statement_date', 'address_proof_date', 'admission_date')
    @classmethod
    def valid_date(cls, value):
        if value and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) or date.fromisoformat(value) > date.today()):
            raise ValueError('Captura una fecha real, no futura, en formato AAAA-MM-DD.')
        return value

    @field_validator('event_date')
    @classmethod
    def valid_event_date(cls, value):
        if value:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Captura la fecha del evento en formato AAAA-MM-DD.')
            date.fromisoformat(value)
        return value

    @field_validator('patient_curp')
    @classmethod
    def valid_curp(cls, value):
        value = value.upper()
        if value and not re.fullmatch(r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d', value):
            raise ValueError('Verifica la CURP del paciente.')
        return value


def is_claim(data):
    return data.get('workflow') == 'reembolso_gmm' or hospital.is_hospital(data)


def review_checks(data):
    return hospital.review_checks(data) if hospital.is_hospital(data) else REVIEW_CHECKS


def workflow_label(data):
    return hospital.WORKFLOWS.get(data.get('workflow'), 'Reembolso GMM' if is_claim(data) else 'Emisión GMM')


def bank_needed(data):
    return data.get('claim_stage') == 'initial' or data.get('bank_changed') is True


def questions(data):
    """Unknown is distinct from no; unanswered conditions cannot suppress requirements."""
    if hospital.is_hospital(data):
        return hospital.questions(data)
    fields = [
        ('claim_stage', 'Tipo de reembolso', '¿Es la primera reclamación de este padecimiento o un complemento de un siniestro existente?'),
        ('policy_number', 'Número de póliza', '¿Cuál es el número de póliza? Consúltalo en la carátula.'),
        ('contractor_name', 'Contratante de la póliza', '¿Quién figura como contratante en la carátula? Puede ser distinto del titular.'),
        ('paternal_surname', 'Apellido paterno del titular', '¿Cuál es el apellido paterno del asegurado titular?'),
        ('given_names', 'Nombres del titular', '¿Cuáles son los nombres del asegurado titular, sin apellidos?'),
        ('rfc', 'RFC del titular', '¿Cuál es el RFC del asegurado titular? Debe corresponder a sus comprobantes.'),
        ('patient_paternal_surname', 'Apellido paterno del paciente', '¿Cuál es el apellido paterno del paciente? No asumas que es el titular.'),
        ('patient_given_names', 'Nombres del paciente', '¿Cuáles son los nombres del paciente, sin apellidos?'),
        ('patient_minor', 'Edad del paciente', '¿El paciente es menor de edad?'),
        ('patient_has_curp', 'CURP disponible del paciente', '¿El paciente tiene CURP?'),
        ('responding_request', 'Respuesta a requerimiento', '¿Este envío responde a información solicitada por MetLife en un trámite previo?'),
        ('includes_medicines', 'Gastos de medicamentos', '¿Se están reclamando medicamentos?'),
        ('includes_studies', 'Estudios realizados', '¿Hay estudios de laboratorio o gabinete relacionados con esta reclamación?'),
        ('includes_histopathology', 'Biopsia o resección', '¿Se realizó biopsia o resección parcial o total de un órgano? Confírmalo con el informe médico.'),
        ('invoices_itemized', 'Desglose de facturas', '¿Todas las facturas detallan conceptos y costos unitarios?'),
        ('digital_signature', 'Firma digital', '¿La solicitud se firmará digitalmente mediante la herramienta autorizada por MetLife?'),
        ('medical_report_date', 'Fecha del informe médico', '¿Qué fecha tiene el informe médico firmado? Si hay varios, captura la más antigua y revisa cada uno.'),
        ('address_proof_date', 'Fecha del comprobante de domicilio', '¿Qué fecha tiene el comprobante de domicilio?'),
    ]
    if data.get('claim_stage') == 'complement':
        fields[1:1] = [('claim_number', 'Número de siniestro', '¿Cuál es el número del siniestro al que corresponde este complemento?'),
                       ('bank_changed', 'Cambio de cuenta bancaria', '¿Cambió la cuenta bancaria respecto del trámite anterior?')]
    if data.get('responding_request'):
        fields.append(('previous_dcn', 'DCN del trámite anterior', '¿Cuál es el folio DCN de la solicitud de información?'))
    if bank_needed(data):
        fields += [('bank_statement_date', 'Fecha del estado de cuenta', '¿Qué fecha tiene el estado de cuenta bancario?'),
                   ('bank_holder_complete', 'Nombre del cuentahabiente', '¿El estado de cuenta muestra el nombre completo del cuentahabiente?')]
    return [{'key': k, 'label': label, 'question': question, 'page': 1 if k in TEXT_MAP else 2,
             'required_for_draft': k in DRAFT_REQUIRED} for k, label, question in fields]


def requirements(data):
    if hospital.is_hospital(data):
        return hospital.requirements(data)
    result = ['Solicitud de reclamación GMM firmada', 'Informe médico firmado por cada médico tratante',
              'Facturas PDF', 'Facturas XML', 'Comprobante de domicilio']
    if data.get('claim_stage') == 'initial':
        result += ['Identificación oficial del titular', 'CURP del titular']
        if data.get('patient_minor') is False:
            result.append('Identificación oficial del paciente')
        if data.get('patient_has_curp') is True:
            result.append('CURP del paciente')
        elif data.get('patient_minor') is True and data.get('patient_has_curp') is False:
            result += ['Acta de nacimiento del paciente', 'Identificación de los padres o representantes']
    if bank_needed(data):
        result.append('Estado de cuenta bancario')
        if data.get('bank_holder_complete') is False:
            result.append('Contrato de la cuenta bancaria')
    if data.get('includes_medicines'):
        result.append('Receta médica desglosada')
    if data.get('includes_studies'):
        result.append('Resultados e interpretación de estudios')
    if data.get('includes_histopathology'):
        result.append('Reporte histopatológico')
    if data.get('invoices_itemized') is False:
        result.append('Desglose de gastos por concepto y costo unitario')
    if data.get('digital_signature'):
        result.append('Fotografías del titular sosteniendo identificación por ambos lados')
    if data.get('responding_request'):
        result.append('Requerimiento de MetLife y respuesta')
    return result


def unanswered(data, key):
    return data.get(key) is None or data.get(key) == ''


def _older_than(value, months):
    today = date.today()
    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
    cutoff = date(year, month + 1, min(today.day, calendar.monthrange(year, month + 1)[1]))
    try:
        return date.fromisoformat(value) < cutoff
    except (TypeError, ValueError):
        return True


def missing_data(data):
    if hospital.is_hospital(data):
        return hospital.missing_data(data)
    result = [f['label'] for f in questions(data) if unanswered(data, f['key'])]
    if data.get('claim_stage') == 'complement' and data.get('medical_report_date') and _older_than(data['medical_report_date'], 6):
        result.append('Actualizar informe médico: supera seis meses')
    if bank_needed(data) and data.get('bank_statement_date') and _older_than(data['bank_statement_date'], 3):
        result.append('Actualizar estado de cuenta: el piloto aplica tres meses por discrepancia entre PDF y portal')
    if data.get('address_proof_date') and _older_than(data['address_proof_date'], 3):
        result.append('Actualizar comprobante de domicilio: supera tres meses')
    if data.get('patient_minor') is False and data.get('patient_has_curp') is False:
        result.append('Resolver CURP del paciente adulto con mesa')
    return result


TEXT_MAP = {
    'contractor_name': 'Nombre del Contratante o razón social',
    'paternal_surname': 'Apellido paterno', 'maternal_surname': 'Apellido materno', 'given_names': 'Nombres',
    'curp': 'CURP1', 'policy_number': 'Póliza', 'phone': 'Celular',
    'patient_paternal_surname': 'Apellido paterno_2', 'patient_maternal_surname': 'Apellido materno_2',
    'patient_given_names': 'Nombres_2', 'patient_curp': 'CURP2',
}
DRAFT_REQUIRED = {'claim_stage', 'policy_number', 'contractor_name', 'paternal_surname', 'given_names', 'rfc',
                  'patient_paternal_surname', 'patient_given_names'}


def progress(data):
    fields = questions(data)
    pending = [f for f in fields if unanswered(data, f['key'])]
    return {'supported': True, 'form_id': 'reclamacion_gmm', 'version': FORMS['claim']['version'],
            'pending_fields': pending, 'filled_count': len(fields)-len(pending), 'mapped_count': len(fields),
            'next_question': pending[0]['question'] if pending else 'Revisa las fechas y los documentos; completa las secciones restantes del formato antes de enviarlo a mesa.',
            'next_field': pending[0]['key'] if pending else None,
            'ready_for_partial_draft': not any(unanswered(data, key) for key in DRAFT_REQUIRED) and
                (data.get('claim_stage') != 'complement' or bool(data.get('claim_number'))),
            'manual_sections': [
                {'id': 'identity', 'title': 'Identidad y domicilio', 'pages': '1', 'question': 'Revisa titular y paciente por separado; completa nacimiento, nacionalidad, ocupación, domicilio y certificado/parentesco.'},
                {'id': 'clinical', 'title': 'Antecedentes y relato del asegurado', 'pages': '2–3', 'question': 'El asegurado debe confirmar antecedentes, otras pólizas, motivo, fechas y relato. No deduzcas respuestas clínicas ni declaraciones.'},
                {'id': 'invoices', 'title': 'Relación de facturas y pago', 'pages': '3', 'question': ('Honorarios y gastos deben revisarse según el trámite; no se autocompleta información bancaria del titular.' if hospital.is_hospital(data) else 'Relaciona cada factura PDF con su XML, revisa RFC del titular, conceptos, importes y suma. Confirma forma de pago y CLABE directamente con el titular; no se autocompletan.')},
                {'id': 'sign', 'title': 'Declaraciones, privacidad y firma', 'pages': '4–6', 'question': 'El titular debe leer y completar las declaraciones y firmar por un medio autorizado. No se marcan consentimientos ni firmas automáticamente.'},
                {'id': 'medical', 'title': 'Informe médico (documento separado)', 'pages': '1–4', 'question': 'Cada médico tratante debe completar antecedentes, diagnóstico, tratamiento, fechas, datos profesionales y firma. Usa «Leer documento o escaneo» para localizar omisiones; la revisión clínica corresponde al médico y a mesa.'},
            ]}


def state_path(workflow='reembolso_gmm'):
    from services.mesa_documents import status_path
    suffix = '-claims' if workflow == 'reembolso_gmm' else '-' + workflow
    return status_path().with_name(status_path().stem + suffix + '.json')


def status(workflow='reembolso_gmm'):
    try:
        state = json.loads(state_path(workflow).read_text())
        checked = datetime.fromisoformat(state.get('checked_at', ''))
        stale = (datetime.now(timezone.utc)-checked).total_seconds() > 7*86400
    except (ValueError, TypeError, OSError):
        state, stale = {}, True
    return {**state, 'stale': stale, 'can_generate': state.get('status') == 'verified' and not stale,
            'version': FORMS['claim']['version'], 'source_url': CLAIM_URL, 'medical_url': hospital.DIRECT_MEDICAL_URL if workflow == 'pago_directo_gmm' else MEDICAL_URL,
            'medical_version': FORMS['medical']['version'], 'source_page': source_page(workflow), 'consent_url': hospital.CONSENT_URL if workflow in hospital.WORKFLOWS else None,
            'notice': state.get('notice', 'Falta verificar las fuentes oficiales del trámite.')}


def source_page(workflow):
    return {'cirugia_programada_gmm': hospital.SURGERY_PAGE, 'pago_directo_gmm': hospital.DIRECT_PAGE}.get(workflow, SOURCE_PAGE)


def check_sources(workflow='reembolso_gmm'):
    from html.parser import HTMLParser
    from services.mesa_documents import _bounded_get
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links = set()
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.links.add(urljoin(source_page(workflow), dict(attrs).get('href', '')))
    state = {'checked_at': datetime.now(timezone.utc).isoformat(), 'forms': {}}
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            parser = Links(); parser.feed(_bounded_get(client, source_page(workflow)).decode('utf-8'))
            forms = {key: dict(form) for key, form in FORMS.items()}
            if workflow in hospital.WORKFLOWS:
                forms['consent'] = hospital.CONSENT_FORM
            if workflow == 'pago_directo_gmm':
                forms['medical']['source_url'] = hospital.DIRECT_MEDICAL_URL
            for key, form in forms.items():
                if form['source_url'] not in parser.links:
                    raise ValueError('official link changed')
                digest = hashlib.sha256(_bounded_get(client, form['source_url'])).hexdigest()
                state['forms'][key] = {'observed_sha256': digest, 'expected_sha256': form['sha256']}
                if digest != form['sha256']:
                    raise ValueError('official content changed')
        state.update(status='verified', notice='Formatos y enlaces verificados en la fuente oficial.')
    except ValueError:
        state.update(status='changed', notice='Cambió un formato o enlace oficial del trámite. Revisa su versión antes de generar.')
    except Exception:
        state.update(status='unavailable', notice='No se pudo verificar la fuente oficial del trámite.')
    path = state_path(workflow); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(state, ensure_ascii=False)); temp.replace(path)
    return state


def generate(data, case_id, revision):
    state = status(data.get('workflow', 'reembolso_gmm'))
    if not state['can_generate']:
        raise HTTPException(409, state['notice'] + (' La comprobación venció.' if state['stale'] else ''))
    if not is_claim(data) or not progress(data)['ready_for_partial_draft']:
        raise HTTPException(422, 'Completa titular, paciente, póliza y tipo de reclamación; un complemento requiere número de siniestro.')
    source = (ASSETS / FORMS['claim']['file']).read_bytes()
    if hashlib.sha256(source).hexdigest() != FORMS['claim']['sha256']:
        raise HTTPException(409, 'El PDF local no coincide con la versión verificada.')
    reader = PdfReader(io.BytesIO(source)); writer = PdfWriter(); writer.clone_document_from_reader(reader)
    fields = writer.get_fields() or {}
    # The source includes an example date. Clear every original value, including dates
    # and consent checkboxes, before filling only confirmed, allowlisted data.
    values = {key: '/Off' if field.get('/FT') == '/Btn' else '' for key, field in fields.items()}
    values.update({pdf: data[key] for key, pdf in TEXT_MAP.items() if data.get(key)})
    if data.get('phone'):
        phone = re.sub(r'[() -]', '', data['phone'])
        if phone.startswith('+52'):
            phone = phone[3:]
        if not re.fullmatch(r'\d{10}', phone):
            raise HTTPException(422, 'El campo celular admite diez dígitos mexicanos. Revisa el teléfono o complétalo manualmente.')
        values['Celular'] = phone
    rfc = data['rfc']
    values.update({'Registro Federal de Contribuyentes RFC': rfc[:10], 'undefined': rfc[10:],
                   {'reembolso_gmm': 'REMBOLSO', 'cirugia_programada_gmm': 'PROGRAMACION', 'pago_directo_gmm': 'INGRRESO'}[data['workflow']]: '/Yes', 'PRIMERA': '/Yes' if data['claim_stage'] == 'initial' else '/Off',
                   'SUBSECUENTE': '/Yes' if data['claim_stage'] == 'complement' else '/Off'})
    if data['claim_stage'] == 'complement':
        values['NUMSIN'] = data['claim_number']
    if data.get('responding_request') is not None:
        values['SIENVIO' if data['responding_request'] else 'NOENVIO'] = '/Yes'
        if data['responding_request']:
            values['DCN'] = data.get('previous_dcn', '')
    if data.get('email'):
        values['undefined_2'], values['undefined_3'] = data['email'].rsplit('@', 1)
    if set(values)-set(fields):
        raise HTTPException(409, 'El mapeo no coincide con los campos oficiales.')
    # Keep canonical parents, but discard duplicate kids not referenced by any page.
    # The published file has both live and off-page widgets under several parents.
    live_widgets = {ref.idnum for page in writer.pages for ref in page.get('/Annots', [])
                    if ref.get_object().get('/Subtype') == '/Widget'}
    for ref in writer.root_object['/AcroForm']['/Fields']:
        field = ref.get_object(); key = field.get('/T')
        if key not in values:
            raise HTTPException(409, 'El árbol de campos oficial requiere revisión.')
        value = values[key]
        field[NameObject('/V')] = NameObject(value) if field.get('/FT') == '/Btn' else TextStringObject(value)
        field.pop('/DV', None)
        if '/Kids' in field:
            field[NameObject('/Kids')] = ArrayObject([kid for kid in field['/Kids'] if kid.idnum in live_widgets])
    # Some official rectangles are inverted; normalize them without moving fields.
    for page in writer.pages:
        for ref in page.get('/Annots', []):
            widget = ref.get_object()
            if widget.get('/Subtype') != '/Widget':
                continue
            field = widget.get('/Parent', widget).get_object(); key = field.get('/T')
            x1, y1, x2, y2 = map(float, widget['/Rect'])
            widget[NameObject('/Rect')] = ArrayObject([FloatObject(min(x1,x2)), FloatObject(min(y1,y2)), FloatObject(max(x1,x2)), FloatObject(max(y1,y2))])
            if field.get('/FT') == '/Tx' and values.get(key):
                value = values[key]
                if any(ord(c) > 255 for c in value) or stringWidth(value, 'Helvetica', 9) > abs(x2-x1)-4:
                    raise HTTPException(422, 'Un dato no cabe en el campo oficial. Revísalo o complétalo manualmente: ' + key)
            if field.get('/FT') == '/Tx':
                for inherited in ('/MaxLen', '/Ff'):
                    if inherited in field:
                        widget[NameObject(inherited)] = field[inherited]
                widget[NameObject('/DA')] = TextStringObject('/Helvetica 9 Tf 0 g')
                field[NameObject('/DA')] = TextStringObject('/Helvetica 9 Tf 0 g')
    writer.update_page_form_field_values(None, {k: (v, '/Helvetica', 9) if fields[k].get('/FT') == '/Tx' else v for k,v in values.items()}, auto_regenerate=False)
    for page in writer.pages:
        stamp = io.BytesIO(); canvas = Canvas(stamp, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
        canvas.setFillColorRGB(.65,.1,.1); canvas.setFont('Helvetica', 7)
        canvas.drawString(15, float(page.mediabox.height)-12, f'BORRADOR PARCIAL - REQUIERE REVISION Y FIRMA | Mesa {case_id[:8]} v{revision}')
        canvas.showPage(); canvas.save(); page.merge_page(PdfReader(io.BytesIO(stamp.getvalue())).pages[0])
    output = io.BytesIO(); writer.write(output); result = output.getvalue()
    checked = PdfReader(io.BytesIO(result)).get_fields() or {}
    if any(str(checked.get(k, {}).get('/V', '')) != v for k,v in values.items()):
        raise HTTPException(500, 'No se pudo verificar el llenado del borrador.')
    return result, {'source_url': CLAIM_URL, 'template_sha256': FORMS['claim']['sha256'],
                    'version': FORMS['claim']['version'], 'case_revision': revision,
                    'fields': {k:v for k,v in values.items() if v and v != '/Off'}, 'partial': True}
