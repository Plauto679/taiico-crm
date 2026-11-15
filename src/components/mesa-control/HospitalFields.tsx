'use client';
import { type ClaimData, claimTextFields, claimConditions, hospitalTextFields, hospitalConditions, workflowLabels } from './ReimbursementFields';
const field = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 disabled:bg-slate-100';
export function HospitalFields({ data, disabled, onChange }: { data: ClaimData; disabled: boolean; onChange: (patch: Partial<ClaimData>) => void }) {
    const surgery = data.workflow === 'cirugia_programada_gmm';
    const textFields = { ...claimTextFields, ...hospitalTextFields };
    const conditions = { ...claimConditions, ...hospitalConditions };
    return <fieldset className="space-y-4 rounded-xl border border-sky-200 bg-sky-50 p-4 sm:col-span-2">
        <legend className="px-1 font-semibold">{workflowLabels[data.workflow]} · Datos del evento y paciente</legend>
        <p className="text-sm">Confirma titular y paciente por separado. «Por confirmar» mantiene un dato pendiente. La mesa contrasta condiciones y excepciones con la póliza; este registro no autoriza cobertura.</p>
        {!surgery && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Ante una emergencia, busca atención médica sin esperar a completar Mesa. El hospital debe reportar el ingreso a MetLife; guardarlo aquí no realiza ese reporte.</p>}
        <label className="block text-sm">Etapa de la reclamación<select aria-label="Etapa de la reclamación" className={field} disabled={disabled} value={data.claim_stage} onChange={e => onChange({ claim_stage: e.target.value as ClaimData['claim_stage'] })}><option value="">Por confirmar</option><option value="initial">Inicial</option><option value="complement">Complemento de siniestro existente</option></select></label>
        {!surgery && <label className="block text-sm">Etapa hospitalaria<select aria-label="Etapa hospitalaria" className={field} disabled={disabled} value={data.hospital_phase} onChange={e => onChange({ hospital_phase: e.target.value as ClaimData['hospital_phase'] })}><option value="">Por confirmar</option><option value="admission">Ingreso</option><option value="stay">Estancia</option><option value="discharge">Egreso</option></select></label>}
        <div className="grid gap-3 sm:grid-cols-2">{Object.entries(textFields).map(([key, label]) => {
            if (key === 'bank_statement_date' || (key === 'address_proof_date' && !surgery) || (key === 'event_date' && !surgery) || (key === 'admission_date' && surgery) || (key === 'claim_number' && data.claim_stage !== 'complement') || (key === 'previous_dcn' && !data.responding_request)) return null;
            return <label key={key} className="text-sm">{label}<input className={field} disabled={disabled} type={key.endsWith('_date') ? 'date' : 'text'} maxLength={key === 'hospital_name' ? 180 : key === 'contractor_name' ? 150 : key.includes('curp') ? 18 : key.includes('names') ? 80 : 60} value={data[key as keyof typeof textFields]} onChange={e => onChange({ [key]: e.target.value })} /></label>;
        })}</div>
        <div className="grid gap-3 sm:grid-cols-2">{Object.entries(conditions).map(([key, label]) => {
            if (['includes_medicines', 'invoices_itemized', 'bank_holder_complete', 'bank_changed'].includes(key) || (surgery && ['has_surgery_pass', 'hospital_reported', 'stay_over_24h', 'mp_required'].includes(key)) || (key === 'doctors_accept_tariff' && data.doctors_in_network !== false)) return null;
            const value = data[key as keyof typeof conditions];
            return <label key={key} className="text-sm">{label}<select aria-label={label} className={field} disabled={disabled} value={value === null ? '' : value ? 'yes' : 'no'} onChange={e => onChange({ [key]: e.target.value === '' ? null : e.target.value === 'yes' })}><option value="">Por confirmar</option><option value="yes">Sí</option><option value="no">No</option></select></label>;
        })}</div>
        <p className="text-xs text-slate-600">{surgery ? 'La fecha y el hospital deben coincidir con el informe médico. MetLife indica al menos 10 días de anticipación. Si el plazo es menor, coordina con mesa el canal y seguimiento; no hay garantía de autorización.' : 'Puedes guardar el expediente desde el ingreso e ir completándolo. Para enviarlo a revisión se requieren los documentos de la etapa seleccionada. La estancia de 24 horas y las excepciones se contrastan con la póliza.'} El informe médico lo completa y firma cada médico; el consentimiento se revisa y firma por el medio que corresponda.</p>
    </fieldset>;
}
