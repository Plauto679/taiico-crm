'use client';

import { FormEvent, useState } from 'react';
import { ClipboardPlus, Loader2, Plus, X } from 'lucide-react';

import { PendingRow } from '@/lib/types/pendientes';
import {
    createEmisionServiciosPending,
    createSiniestrosPending,
} from '@/modules/pendientes/service';


type PendingSourceKey = 'emision-servicios' | 'siniestros';

interface RegisterPendingModalProps {
    source: PendingSourceKey;
    onClose: () => void;
    onCreated: (row: PendingRow) => void;
}

const GMM_REQUESTS = [
    'EMISION PERSONA FISICA',
    'EMISION PERSONA MORAL',
    'Modificación de nombre y apellidos GMM',
    'Cambio de contratante GMM',
    'Cambio de domicilio GMM',
    'Corrección RFC GMM',
    'Cambio de beneficiario GMM',
    'Duplicado de póliza GMM',
    'Duplicado de endoso GMM',
    'Cambio clave de agente',
    'Reconocimiento de antigüedad',
    'Rehabilitación GMM',
    'Cambio de conducto de cobro (Débito o crédito)',
    'Cambio de conducto de cobro (Conducto Agente)',
    'Cambio de forma de pago GMM',
    'Inclusión/Exclusión De Coberturas GMM',
    'Inclusión/Exclusión De Dependientes GMM',
    'Cancelación de pólizas GMM',
    'Aclaración de pagos GMM',
    'Aplicación de pagos GMM',
    'Reembolso GMM',
];

const VIDA_REQUESTS = [
    'EMISION PERSONA FISICA',
    'EMISION PERSONA MORAL',
    'Modificación de nombre y apellidos VIDA',
    'Cambio de contratante VIDA',
    'Cambio de domicilio VIDA',
    'Corrección RFC VIDA',
    'Cambio de beneficiario VIDA',
    'Duplicado de póliza GMM',
    'Cambio clave de agente VIDA',
    'Rehabilitación VIDA',
    'Cambio de conducto de cobro (Débito o crédito)',
    'Cambio de conducto de cobro (Conducto Agente)',
    'Duplicado de recibo VIDA',
    'Cambio de forma de pago VIDA',
    'Corrección de edad / Corrección fecha de nacimiento VIDA',
    'Inclusión/Exclusión De Coberturas VIDA',
    'Rescate total / parcial VIDA',
    'Devolución de primas VIDA',
    'Aclaración de pagos VIDA',
    'Aplicación de pagos VIDA',
];

export function RegisterPendingModal({ source, onClose, onCreated }: RegisterPendingModalProps) {
    const [asegurado, setAsegurado] = useState('');
    const [rfc, setRfc] = useState('');
    const [poliza, setPoliza] = useState('');
    const [casificacion, setCasificacion] = useState<'Vida' | 'GMM' | ''>('');
    const [tipoTramite, setTipoTramite] = useState('');
    const [solicitudesDe, setSolicitudesDe] = useState<string[]>(['']);
    const [tramite, setTramite] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const response = source === 'emision-servicios'
                ? await createEmisionServiciosPending({
                    asegurado,
                    rfc,
                    poliza,
                    casificacion: casificacion as 'Vida' | 'GMM',
                    tipo_tramite: tipoTramite as 'Servicios' | 'Emisión',
                    solicitud_de: solicitudesDe.filter(Boolean).join(', '),
                })
                : await createSiniestrosPending({
                    asegurado,
                    rfc,
                    tipo_tramite: tipoTramite as 'Cirugía Progamada' | 'Reembolso' | 'Programación de Medicamentos' | 'Programación de estudios/terapias',
                    tramite: tramite as 'Complemento' | 'Reconsideración' | 'Garantías',
                });
            onCreated(response.row);
        } catch (submissionError) {
            setError(submissionError instanceof Error ? submissionError.message : 'No fue posible registrar el pendiente.');
        } finally {
            setSaving(false);
        }
    };

    const requestOptions = casificacion === 'GMM' ? GMM_REQUESTS : casificacion === 'Vida' ? VIDA_REQUESTS : [];
    const updateSolicitud = (index: number, value: string) => {
        setSolicitudesDe((current) => current.map((item, itemIndex) => itemIndex === index ? value : item));
    };
    const removeSolicitud = (index: number) => {
        setSolicitudesDe((current) => current.filter((_, itemIndex) => itemIndex !== index));
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={onClose}>
            <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
                <div className="flex items-center justify-between border-b border-slate-200 p-5">
                    <div className="flex items-center gap-3">
                        <div className="rounded-full bg-blue-100 p-2 text-blue-700"><ClipboardPlus className="h-5 w-5" /></div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Registrar Pendiente</h2>
                            <p className="text-sm text-slate-500">{source === 'emision-servicios' ? 'Emisión y Servicios' : 'Siniestros'}</p>
                        </div>
                    </div>
                    <button type="button" onClick={onClose} disabled={saving} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar"><X className="h-5 w-5" /></button>
                </div>

                <form onSubmit={submit} className="p-5">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <TextField label="Nombre del Asegurado" value={asegurado} onChange={setAsegurado} />
                        <TextField label="RFC" value={rfc} onChange={(value) => setRfc(value.toUpperCase())} required={false} />
                        {source === 'emision-servicios' ? (
                            <>
                                <TextField label="Póliza" value={poliza} onChange={setPoliza} required={false} />
                                <SelectField label="Casificación" value={casificacion} onChange={(value) => { setCasificacion(value as 'Vida' | 'GMM'); setSolicitudesDe(['']); }} options={['Vida', 'GMM']} />
                                <SelectField label="Tipo de Trámite" value={tipoTramite} onChange={setTipoTramite} options={['Servicios', 'Emisión']} />
                                <div className="sm:col-span-2">
                                    <span className="text-sm font-medium text-slate-700">Solicitud de</span>
                                    <div className="mt-1.5 space-y-2">
                                        {solicitudesDe.map((solicitud, index) => (
                                            <div key={index} className="flex items-center gap-2">
                                                <select
                                                    required
                                                    value={solicitud}
                                                    onChange={(event) => updateSolicitud(index, event.target.value)}
                                                    disabled={!casificacion}
                                                    className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-400"
                                                >
                                                    <option value="">Seleccionar...</option>
                                                    {requestOptions
                                                        .filter((option) => option === solicitud || !solicitudesDe.includes(option))
                                                        .map((option) => <option key={option} value={option}>{option}</option>)}
                                                </select>
                                                {solicitudesDe.length > 1 && (
                                                    <button type="button" onClick={() => removeSolicitud(index)} className="rounded-lg border border-slate-300 p-2 text-slate-500 hover:bg-red-50 hover:text-red-600" aria-label="Quitar solicitud">
                                                        <X className="h-4 w-4" />
                                                    </button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setSolicitudesDe((current) => [...current, ''])}
                                        disabled={!casificacion || solicitudesDe.some((value) => !value) || solicitudesDe.length >= requestOptions.length}
                                        className="mt-2 inline-flex items-center gap-1 rounded-lg border border-blue-200 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        <Plus className="h-4 w-4" /> Agregar otra solicitud
                                    </button>
                                </div>
                            </>
                        ) : (
                            <>
                                <SelectField label="Tipo de Trámite" value={tipoTramite} onChange={setTipoTramite} options={['Cirugía Progamada', 'Reembolso', 'Programación de Medicamentos', 'Programación de estudios/terapias']} />
                                <SelectField label="Trámite" value={tramite} onChange={setTramite} options={['Complemento', 'Reconsideración', 'Garantías']} />
                            </>
                        )}
                    </div>

                    {error && <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

                    <div className="mt-6 flex justify-end gap-3">
                        <button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">Cancelar</button>
                        <button type="submit" disabled={saving} className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Guardar pendiente
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function TextField({ label, value, onChange, required = true }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
    return (
        <label className="block">
            <span className="text-sm font-medium text-slate-700">{label}{!required && <span className="ml-1 font-normal text-slate-400">(opcional)</span>}</span>
            <input required={required} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
        </label>
    );
}

function SelectField({ label, value, onChange, options, disabled = false }: { label: string; value: string; onChange: (value: string) => void; options: string[]; disabled?: boolean }) {
    return (
        <label className="block">
            <span className="text-sm font-medium text-slate-700">{label}</span>
            <select required value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-400">
                <option value="">Seleccionar...</option>
                {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
        </label>
    );
}
