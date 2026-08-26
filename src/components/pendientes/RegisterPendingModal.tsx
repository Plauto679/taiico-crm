'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, ClipboardPlus, Loader2, Plus, Search, UserRoundPlus, X } from 'lucide-react';

import { PendingAccess, PendingClientOption, PendingRow } from '@/lib/types/pendientes';
import {
    createEmisionServiciosPending,
    createSiniestrosPending,
    getPendingClientDirectory,
} from '@/modules/pendientes/service';
import { agentsForPromotoria, PendingAgentSelect } from './PendingAgentSelect';


type PendingSourceKey = 'emision-servicios' | 'siniestros';

interface RegisterPendingModalProps {
    source: PendingSourceKey;
    onClose: () => void;
    onCreated: (row: PendingRow) => void;
    access: PendingAccess;
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

export function RegisterPendingModal({ source, onClose, onCreated, access }: RegisterPendingModalProps) {
    const [clients, setClients] = useState<PendingClientOption[]>([]);
    const [loadingClients, setLoadingClients] = useState(true);
    const [selectedClient, setSelectedClient] = useState<PendingClientOption | null>(null);
    const [asegurado, setAsegurado] = useState('');
    const [insuredName, setInsuredName] = useState('');
    const [rfc, setRfc] = useState('');
    const [poliza, setPoliza] = useState('');
    const [casificacion, setCasificacion] = useState<'Vida' | 'GMM' | ''>('');
    const [tipoTramite, setTipoTramite] = useState('');
    const [solicitudesDe, setSolicitudesDe] = useState<string[]>(['']);
    const [tramite, setTramite] = useState('');
    const [estatusSiniestro, setEstatusSiniestro] = useState('En Proceso');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [promotoria, setPromotoria] = useState(
        access.promotorias.length === 1 ? access.promotorias[0] : '',
    );
    const [rfcAgente, setRfcAgente] = useState('');
    const [responsable, setResponsable] = useState('');
    const [recordatorioFuturo, setRecordatorioFuturo] = useState('');
    const requestId = useRef<string | null>(null);
    const submissionInProgress = useRef(false);

    useEffect(() => {
        let active = true;
        getPendingClientDirectory()
            .then((directory) => { if (active) setClients(directory); })
            .catch((directoryError) => {
                if (active) setError(directoryError instanceof Error ? directoryError.message : 'No fue posible consultar Clientes.');
            })
            .finally(() => { if (active) setLoadingClients(false); });
        return () => { active = false; };
    }, []);

    const clientMatches = useMemo(() => {
        const term = asegurado.trim().toLocaleLowerCase('es-MX');
        if (!term || selectedClient) return [];
        return clients.filter((client) =>
            client.nombre.toLocaleLowerCase('es-MX').includes(term)
            || client.rfc.toLocaleLowerCase('es-MX').includes(term)
        ).slice(0, 8);
    }, [asegurado, clients, selectedClient]);

    const chooseClient = (client: PendingClientOption) => {
        setSelectedClient(client);
        setAsegurado(client.nombre);
        setRfc(client.rfc || '');
    };

    const changeClient = () => {
        setSelectedClient(null);
        setAsegurado('');
        setRfc('');
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (submissionInProgress.current) return;
        submissionInProgress.current = true;
        requestId.current ||= crypto.randomUUID();
        setSaving(true);
        setError(null);
        try {
            const response = source === 'emision-servicios'
                ? await createEmisionServiciosPending({
                    request_id: requestId.current,
                    client_id: selectedClient?.id || '',
                    asegurado,
                    insured_name: insuredName,
                    rfc,
                    poliza,
                    casificacion: casificacion as 'Vida' | 'GMM',
                    tipo_tramite: tipoTramite as 'Servicios' | 'Emisión',
                    solicitud_de: solicitudesDe.filter(Boolean).join(', '),
                    promotoria,
                    rfc_agente: rfcAgente,
                    responsable,
                    recordatorio_futuro: recordatorioFuturo,
                })
                : await createSiniestrosPending({
                    request_id: requestId.current,
                    client_id: selectedClient?.id || '',
                    asegurado,
                    insured_name: insuredName,
                    rfc,
                    poliza,
                    tipo_tramite: tipoTramite as 'Cirugía Progamada' | 'Reembolso' | 'Programación de Medicamentos' | 'Programación de estudios/terapias',
                    tramite: tramite as 'Complemento' | 'Reconsideración' | 'Garantías',
                    estatus: estatusSiniestro as 'En Proceso' | 'Pagado' | 'Rechazado' | 'Suspendido',
                    promotoria,
                    rfc_agente: rfcAgente,
                    responsable,
                    recordatorio_futuro: recordatorioFuturo,
                });
            if (response.notification_warning) {
                window.alert(response.notification_warning);
            }
            onCreated(response.row);
        } catch (submissionError) {
            setError(submissionError instanceof Error ? submissionError.message : 'No fue posible registrar el pendiente.');
        } finally {
            submissionInProgress.current = false;
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
    const updatePromotoria = (value: string) => {
        setPromotoria(value);
        if (!agentsForPromotoria(access.agents, value).some((agent) => agent.rfc === rfcAgente)) {
            setRfcAgente('');
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto overscroll-contain bg-slate-950/50 p-2 sm:p-4" onMouseDown={onClose}>
            <div className="flex max-h-[calc(100dvh-1rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl sm:max-h-[calc(100dvh-2rem)]" onMouseDown={(event) => event.stopPropagation()}>
                <div className="flex shrink-0 items-center justify-between border-b border-slate-200 p-4 sm:p-5">
                    <div className="flex items-center gap-3">
                        <div className="rounded-full bg-blue-100 p-2 text-blue-700"><ClipboardPlus className="h-5 w-5" /></div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Registrar Pendiente</h2>
                            <p className="text-sm text-slate-500">{source === 'emision-servicios' ? 'Emisión y Servicios' : 'Siniestros'}</p>
                        </div>
                    </div>
                    <button type="button" onClick={onClose} disabled={saving} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar"><X className="h-5 w-5" /></button>
                </div>

                <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
                    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 [-webkit-overflow-scrolling:touch] sm:p-5">
                        <div className="grid gap-4 sm:grid-cols-2">
                            <div className="sm:col-span-2 rounded-xl border border-blue-200 bg-blue-50/60 p-4">
                                <div className="mb-3">
                                    <p className="font-bold text-slate-900">Contratante o prospecto</p>
                                    <p className="text-sm text-slate-600">Busca primero en el registro maestro por nombre o RFC. Si no existe, escribe su nombre para registrarlo como prospecto.</p>
                                </div>
                                {selectedClient ? (
                                    <div className="rounded-lg border border-emerald-200 bg-white p-3">
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                            <div>
                                                <p className="flex items-center gap-2 font-semibold text-emerald-800"><CheckCircle2 className="h-4 w-4" /> Contratante seleccionado</p>
                                                <p className="mt-1 font-bold text-slate-900">{selectedClient.nombre}</p>
                                                <p className="text-sm text-slate-600">{selectedClient.rfc || 'Prospecto sin RFC'}</p>
                                            </div>
                                            <button type="button" onClick={changeClient} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cambiar cliente</button>
                                        </div>
                                        {!selectedClient.rfc && (
                                            <label className="mt-3 block border-t border-slate-100 pt-3">
                                                <span className="text-sm font-medium text-slate-700">Asignar RFC al prospecto <span className="font-normal text-slate-400">(opcional)</span></span>
                                                <input value={rfc} onChange={(event) => setRfc(event.target.value.toUpperCase())} placeholder="Al capturarlo se creará su expediente único" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                                            </label>
                                        )}
                                    </div>
                                ) : (
                                    <div className="relative">
                                        <label className="block">
                                            <span className="text-sm font-medium text-slate-700">Buscar o capturar contratante</span>
                                            <div className="relative mt-1.5">
                                                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                                                <input required autoComplete="off" value={asegurado} onChange={(event) => setAsegurado(event.target.value)} placeholder="Nombre o RFC del cliente" className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                                            </div>
                                        </label>
                                        {loadingClients && <p className="mt-2 text-xs text-slate-500">Consultando registro maestro…</p>}
                                        {clientMatches.length > 0 && (
                                            <div className="mt-2 max-h-52 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                                                {clientMatches.map((client) => (
                                                    <button key={client.id} type="button" onClick={() => chooseClient(client)} className="flex w-full items-center justify-between gap-3 border-b border-slate-100 px-3 py-2 text-left last:border-0 hover:bg-blue-50">
                                                        <span><span className="block font-semibold text-slate-900">{client.nombre}</span><span className="block text-xs text-slate-500">{client.rfc || 'Prospecto sin RFC'}</span></span>
                                                        <span className="text-xs font-semibold text-blue-700">Seleccionar</span>
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                        {asegurado.trim() && !loadingClients && clientMatches.length === 0 && (
                                            <p className="mt-2 flex items-center gap-2 text-xs font-medium text-amber-700"><UserRoundPlus className="h-4 w-4" /> Se registrará como prospecto nuevo si no capturas RFC.</p>
                                        )}
                                    </div>
                                )}
                                {!selectedClient && (
                                    <label className="mt-3 block">
                                        <span className="text-sm font-medium text-slate-700">RFC <span className="font-normal text-slate-400">(opcional para prospectos)</span></span>
                                        <input value={rfc} onChange={(event) => setRfc(event.target.value.toUpperCase())} placeholder="Se solicitará antes de crear el expediente" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                                    </label>
                                )}
                            </div>
                            <SelectField
                                label="Promotoría"
                                value={promotoria}
                                onChange={updatePromotoria}
                                options={access.promotorias}
                                disabled={access.promotorias.length === 1}
                            />
                            <label className="block">
                                <span className="text-sm font-medium text-slate-700">RFC Agente</span>
                                <PendingAgentSelect
                                    agents={access.agents}
                                    promotoria={promotoria}
                                    value={rfcAgente}
                                    onChange={setRfcAgente}
                                    className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100 disabled:text-slate-400"
                                />
                            </label>
                            <SelectField
                                label="Responsable"
                                value={responsable}
                                onChange={setResponsable}
                                options={(access.admins || []).map((admin) => admin.email)}
                            />
                            <label className="block">
                                <span className="text-sm font-medium text-slate-700">Recordatorio Futuro <span className="font-normal text-slate-400">(opcional)</span></span>
                                <input type="date" value={recordatorioFuturo} onChange={(event) => setRecordatorioFuturo(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                            </label>
                            {source === 'emision-servicios' ? (
                                <>
                                    <TextField label="Asegurado" value={insuredName} onChange={setInsuredName} required={false} />
                                    <TextField label="Póliza" value={poliza} onChange={setPoliza} required={false} />
                                    <SelectField label="Casificación" value={casificacion} onChange={(value) => { setCasificacion(value as 'Vida' | 'GMM'); setSolicitudesDe(['']); }} options={['Vida', 'GMM']} />
                                    <SelectField label="Tipo de Trámite" value={tipoTramite} onChange={setTipoTramite} options={['Emisión', 'Servicios']} />
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
                                    <TextField label="Asegurado" value={insuredName} onChange={setInsuredName} required={false} />
                                    <TextField label="Póliza" value={poliza} onChange={setPoliza} />
                                    <SelectField label="Tipo de Trámite" value={tipoTramite} onChange={setTipoTramite} options={['Cirugía Progamada', 'Reembolso', 'Programación de Medicamentos', 'Programación de estudios/terapias']} />
                                    <SelectField label="Trámite" value={tramite} onChange={setTramite} options={['Complemento', 'Reconsideración', 'Garantías']} />
                                    <SelectField label="Estatus" value={estatusSiniestro} onChange={setEstatusSiniestro} options={['En Proceso', 'Pagado', 'Rechazado', 'Suspendido']} />
                                </>
                            )}
                        </div>

                        {error && <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
                    </div>

                    <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-slate-200 bg-white p-4 sm:flex-row sm:justify-end sm:gap-3 sm:p-5">
                        <button type="button" onClick={onClose} disabled={saving} className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60 sm:w-auto">Cancelar</button>
                        <button type="submit" disabled={saving} className="inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 sm:w-auto">
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
