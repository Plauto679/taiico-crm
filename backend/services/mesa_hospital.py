"""Preparation rules, not coverage decisions, for surgery and hospital admission."""
from datetime import date

WORKFLOWS = {'cirugia_programada_gmm': 'Cirugía programada GMM', 'pago_directo_gmm': 'Pago directo GMM'}
SURGERY_PAGE = 'https://www.metlife.com.mx/tramites-y-servicios/tramites-de-seguros-de-gastos-medicos/cirugia-programada/'
DIRECT_PAGE = 'https://www.metlife.com.mx/tramites-y-servicios/tramites-de-seguros-de-gastos-medicos/ingreso-hospitalitario/'
CONSENT_URL = 'https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/cirugia-programada/consentimiento-informado-vg-2-142-ver-1.pdf'
DIRECT_MEDICAL_URL = 'https://www.metlife.com.mx/content/dam/metlifecom/mx/pdfs/common-files/CC-1-020-VER5.pdf'
CONSENT_FORM = {'file': 'consentimiento-informado-vg-2-142-v1.pdf', 'source_url': CONSENT_URL,
                'sha256': '2acb9b1f9ceae9cc3822f2bad19d2fa2956d497614f76ad0616e51e273f89042', 'version': 'VG-2-142 VER. 1'}


def is_hospital(data):
    return data.get('workflow') in WORKFLOWS


def questions(data):
    from services.mesa_claims import TEXT_MAP, DRAFT_REQUIRED
    fields = [
        ('claim_stage', 'Etapa de la reclamación', '¿Es un trámite inicial o complemento de un siniestro existente?'),
        ('policy_number', 'Número de póliza', '¿Cuál es la póliza del paciente?'),
        ('contractor_name', 'Contratante de la póliza', '¿Quién contrató la póliza?'),
        ('paternal_surname', 'Apellido paterno del titular', '¿Cuál es el apellido paterno del titular?'),
        ('given_names', 'Nombres del titular', '¿Cuáles son los nombres del titular?'),
        ('rfc', 'RFC del titular', '¿Cuál es el RFC del titular?'),
        ('patient_paternal_surname', 'Apellido paterno del paciente', '¿Cuál es el apellido paterno del paciente?'),
        ('patient_given_names', 'Nombres del paciente', '¿Cuáles son los nombres del paciente?'),
        ('patient_minor', 'Paciente menor de edad', '¿El paciente es menor de edad?'),
        ('patient_has_curp', 'CURP disponible del paciente', '¿El paciente tiene CURP?'),
        ('hospital_name', 'Hospital', '¿En qué hospital se atenderá o está ingresado el paciente?'),
        ('hospital_in_network', 'Hospital y plan', '¿Se verificó que el hospital está en la red aplicable al plan contratado?'),
        ('doctors_in_network', 'Médicos en convenio', '¿Todos los médicos participantes pertenecen al grupo médico asociado?'),
        ('policy_current_paid', 'Vigencia y pago de póliza', '¿Se comprobó que la póliza está vigente y pagada?'),
        ('includes_studies', 'Estudios relacionados', '¿Hay estudios relacionados con el caso?'),
        ('includes_histopathology', 'Biopsia o resección', '¿Se realizó biopsia o resección que requiera reporte histopatológico?'),
        ('digital_signature', 'Firma digital', '¿Se usará firma digital autorizada por MetLife?'),
        ('medical_report_date', 'Fecha del informe médico', '¿Qué fecha tiene el informe médico más antiguo de los que se aportarán?'),
        ('responding_request', 'Respuesta a requerimiento', '¿Se responde a un requerimiento previo de MetLife?'),
    ]
    if data.get('workflow') == 'cirugia_programada_gmm':
        fields += [('event_date', 'Fecha programada del evento', '¿Cuál es la fecha prevista? Debe coincidir con el informe del médico.'),
                   ('address_proof_date', 'Fecha del comprobante de domicilio', '¿Qué fecha tiene el comprobante de domicilio?')]
    else:
        fields += [('admission_date', 'Fecha de ingreso hospitalario', '¿Qué día ingresó el paciente?'),
                   ('hospital_phase', 'Etapa hospitalaria', '¿Está en ingreso, estancia o egreso?'),
                   ('has_surgery_pass', 'Carta pase de cirugía', '¿Este ingreso ya cuenta con carta pase de programación de cirugía?'),
                   ('hospital_reported', 'Reporte del hospital', '¿El hospital confirmó que reportó el ingreso a MetLife?'),
                   ('stay_over_24h', 'Estancia y condiciones', '¿La estancia supera 24 horas? La mesa debe contrastar las excepciones con la póliza.'),
                   ('mp_required', 'Actas del Ministerio Público', '¿El evento requiere actas del Ministerio Público (por ejemplo, accidente vial o lesiones)?')]
    if data.get('doctors_in_network') is False:
        fields.append(('doctors_accept_tariff', 'Aceptación de tabulador', '¿Los médicos fuera de convenio aceptan el tabulador y documentaron sus honorarios?'))
    if data.get('claim_stage') == 'complement':
        fields.append(('claim_number', 'Número de siniestro', '¿A qué siniestro corresponde el complemento?'))
    if data.get('responding_request'):
        fields.append(('previous_dcn', 'DCN del trámite anterior', '¿Cuál es el DCN del requerimiento?'))
    return [{'key': k, 'label': label, 'question': question, 'page': 1 if k in TEXT_MAP else 2,
             'required_for_draft': k in DRAFT_REQUIRED} for k, label, question in fields]


def requirements(data):
    surgery = data.get('workflow') == 'cirugia_programada_gmm'
    result = ['Solicitud de reclamación GMM firmada', 'Informe médico firmado por cada médico tratante']
    if surgery:
        result += ['Comprobante de domicilio']
    else:
        result += ['Credencial de MetLife', 'Expediente clínico completo']
        if data.get('has_surgery_pass') is True:
            result.append('Carta pase de programación de cirugía')
        if data.get('mp_required'):
            result.append('Actas del Ministerio Público')
        if data.get('hospital_phase') == 'discharge':
            result += ['Nota de alta firmada', 'Estado de cuenta hospitalario y desglose']
    # Unknown never suppresses consent; an explicit pass and its attachment are needed.
    if surgery or data.get('has_surgery_pass') is not True:
        result.append('Consentimiento informado firmado')
    # The PDF checklist requests ID also for surgery complements: keep the stricter
    # requirement visible and require administrative comparison with the portal.
    result.append('Identificación oficial del titular')
    if data.get('patient_minor') is False:
        result.append('Identificación oficial del paciente')
    if data.get('claim_stage') == 'initial':
        result.append('CURP del titular')
        if data.get('patient_has_curp') is True:
            result.append('CURP del paciente')
        elif data.get('patient_minor') is True and data.get('patient_has_curp') is False:
            result += ['Acta de nacimiento del paciente', 'Identificación de los padres o representantes']
    if data.get('includes_studies'):
        result.append('Resultados e interpretación de estudios')
    if data.get('includes_histopathology'):
        result.append('Reporte histopatológico')
    if data.get('doctors_in_network') is False:
        result.append('Presupuesto y aceptación de honorarios en informe médico')
    if data.get('digital_signature'):
        result.append('Fotografías del titular sosteniendo identificación por ambos lados')
    if data.get('responding_request'):
        result.append('Requerimiento de MetLife y respuesta')
    return result


def missing_data(data):
    from services.mesa_claims import unanswered, _older_than
    result = [f['label'] for f in questions(data) if unanswered(data, f['key'])]
    if data.get('medical_report_date') and _older_than(data['medical_report_date'], 6):
        result.append('Actualizar informe médico: supera seis meses')
    if data.get('workflow') == 'cirugia_programada_gmm':
        if data.get('address_proof_date') and _older_than(data['address_proof_date'], 3):
            result.append('Actualizar comprobante de domicilio: supera tres meses')
        if data.get('event_date') and date.fromisoformat(data['event_date']) < date.today():
            result.append('Revisar fecha programada: el evento ya pasó')
    if data.get('patient_minor') is False and data.get('patient_has_curp') is False:
        result.append('Resolver CURP del paciente adulto con mesa')
    # Policy exceptions are reviewed explicitly by people, never auto-declined here.
    return result


def notices(data):
    result = ['La mesa prepara y revisa documentos; la cobertura y autorización las determina MetLife.']
    if data.get('workflow') == 'cirugia_programada_gmm':
        result += ['MetLife indica al menos 10 días de anticipación. Confirma con mesa la fecha y el canal; no se garantiza autorización antes del evento.',
                   'El portal limita identificación a trámites iniciales; el checklist del PDF también la pide para programación. El piloto conserva identificación y mesa contrasta el criterio.']
        if data.get('event_date') and 0 <= (date.fromisoformat(data['event_date']) - date.today()).days < 10:
            result.append('El evento está a menos de 10 días: requiere revisión prioritaria de anticipación y canal.')
    else:
        result += ['Ante una emergencia, acude a atención médica; no esperes a completar este expediente. El hospital debe reportar el ingreso a MetLife.',
                   'El portal de ingreso menciona MédicaLife Primordial. Mesa debe contrastar producto, red, vigencia, deducible y estancia con la póliza concreta; la regla de 24 horas puede tener excepciones.']
        if data.get('hospital_reported') is not True:
            result.append('Reporte hospitalario sin confirmar: coordínalo con el hospital; guardar en Mesa no realiza ese reporte.')
    result.append('Las facturas de cirugía/pago directo corresponden a MetLife; no se pide cuenta bancaria del titular como en reembolso.')
    return result


def review_checks(data):
    result = {
        'identity': 'Identidad, póliza, producto y personas contrastados con originales',
        'medical': 'Informes firmados por cada médico, fechas y estudios contrastados; revisión clínica con los médicos',
        'coverage': 'Red para el plan, vigencia, pago, deducible y excepciones contrastados; sin prometer autorización',
        'fees': 'Convenio y honorarios de todos los médicos revisados, incluida aceptación y presupuesto cuando aplica',
        'consent': ('Solicitud y consentimiento firmados por el titular; declaraciones contrastadas' if data.get('workflow') == 'cirugia_programada_gmm' else 'Solicitud y consentimiento firmados, o carta pase que justifica la excepción; firmante revisado según el trámite'),
    }
    if data.get('workflow') == 'cirugia_programada_gmm':
        result['timing'] = 'Lugar y fecha en informe, anticipación y canal revisados; diferencias portal/PDF documentadas en el comentario'
    else:
        result['hospital'] = 'Reporte del ingreso, estancia según póliza, expediente clínico y etapa hospitalaria revisados; pendientes y excepciones documentados en el comentario'
    return result
