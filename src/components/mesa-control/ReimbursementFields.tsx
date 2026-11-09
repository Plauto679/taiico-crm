'use client';

export const claimTextFields = {
    policy_number: 'Número de póliza', contractor_name: 'Contratante que aparece en la póliza',
    claim_number: 'Número de siniestro', previous_dcn: 'DCN del trámite anterior',
    patient_paternal_surname: 'Apellido paterno del paciente', patient_maternal_surname: 'Apellido materno del paciente',
    patient_given_names: 'Nombre(s) del paciente', patient_curp: 'CURP del paciente',
    medical_report_date: 'Fecha del informe médico (la más antigua si hay varios)',
    bank_statement_date: 'Fecha del estado de cuenta bancario', address_proof_date: 'Fecha del comprobante de domicilio',
};
export const claimConditions = {
    patient_minor: '¿El paciente es menor de edad?', patient_has_curp: '¿El paciente tiene CURP?',
    responding_request: '¿Responde a información solicitada por MetLife?', bank_changed: '¿Cambió la cuenta bancaria?',
    includes_medicines: '¿Se reclaman medicamentos?', includes_studies: '¿Hay estudios de laboratorio o gabinete?',
    includes_histopathology: '¿Hubo biopsia o resección parcial o total de un órgano?',
    invoices_itemized: '¿Todas las facturas detallan conceptos y costos unitarios?',
    bank_holder_complete: '¿El estado de cuenta muestra el nombre completo del titular?',
    digital_signature: '¿Se usará firma digital autorizada por MetLife?',
};
export type ClaimData = { workflow: 'emision_gmm' | 'reembolso_gmm'; claim_stage: '' | 'initial' | 'complement' }
    & Record<keyof typeof claimTextFields, string> & Record<keyof typeof claimConditions, boolean | null>;
export const emptyClaim: ClaimData = {
    workflow: 'emision_gmm', claim_stage: '', policy_number: '', contractor_name: '', claim_number: '', previous_dcn: '',
    patient_paternal_surname: '', patient_maternal_surname: '', patient_given_names: '', patient_curp: '',
    medical_report_date: '', bank_statement_date: '', address_proof_date: '',
    patient_minor: null, patient_has_curp: null, responding_request: null, bank_changed: null,
    includes_medicines: null, includes_studies: null, includes_histopathology: null,
    invoices_itemized: null, bank_holder_complete: null, digital_signature: null,
};
const field = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 disabled:bg-slate-100';

export function ReimbursementFields({ data, disabled, onChange }: { data: ClaimData; disabled: boolean; onChange: (patch: Partial<ClaimData>) => void }) {
    const needsBank = data.claim_stage === 'initial' || data.bank_changed === true;
    return <fieldset className="space-y-4 rounded-xl border border-sky-200 bg-sky-50 p-4 sm:col-span-2">
        <legend className="px-1 font-semibold">Reembolso GMM · Datos del trámite y del paciente</legend>
        <p className="text-sm text-slate-600">Confirma las condiciones del caso para definir los documentos. «Por confirmar» mantiene el dato pendiente; no significa «No». El titular, el contratante y el paciente pueden ser personas distintas.</p>
        <label className="block text-sm">Tipo de reembolso<select aria-label="Tipo de reembolso" className={field} disabled={disabled} value={data.claim_stage} onChange={e => onChange({ claim_stage: e.target.value as ClaimData['claim_stage'] })}><option value="">Por confirmar</option><option value="initial">Inicial · Primera reclamación del padecimiento</option><option value="complement">Complemento · Siniestro existente</option></select></label>
        <div className="grid gap-3 sm:grid-cols-2">{Object.entries(claimTextFields).map(([key, label]) => {
            if ((key === 'claim_number' && data.claim_stage !== 'complement') || (key === 'previous_dcn' && !data.responding_request) || (key === 'bank_statement_date' && !needsBank)) return null;
            return <label key={key} className="text-sm">{label}<input className={field} disabled={disabled} type={key.endsWith('_date') ? 'date' : 'text'} maxLength={key.includes('curp') ? 18 : key === 'contractor_name' ? 150 : key.includes('names') ? 80 : 40} value={data[key as keyof typeof claimTextFields]} onChange={e => onChange({ [key]: e.target.value })} /></label>;
        })}</div>
        <div className="grid gap-3 sm:grid-cols-2">{Object.entries(claimConditions).map(([key, label]) => {
            if ((key === 'bank_changed' && data.claim_stage !== 'complement') || (key === 'bank_holder_complete' && !needsBank)) return null;
            const value = data[key as keyof typeof claimConditions];
            return <label key={key} className="text-sm">{label}<select aria-label={label} className={field} disabled={disabled} value={value === null ? '' : value ? 'yes' : 'no'} onChange={e => onChange({ [key]: e.target.value === '' ? null : e.target.value === 'yes' })}><option value="">Por confirmar</option><option value="yes">Sí</option><option value="no">No</option></select></label>;
        })}</div>
        <p className="text-xs text-slate-600">El médico completa y firma su informe. Para complementos, se revisa su actualización cada seis meses. El comprobante de domicilio no debe superar tres meses y, en este piloto, el estado de cuenta requerido tampoco debe superar tres meses: el PDF oficial pide tres y el portal señala seis. Aplicamos el plazo menor mientras mesa confirma el criterio. La mesa verifica las fechas contra los originales.</p>
    </fieldset>;
}
