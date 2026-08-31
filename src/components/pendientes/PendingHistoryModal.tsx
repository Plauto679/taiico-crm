'use client';

import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Check, CheckCircle2, ChevronDown, ExternalLink, File, FolderOpen, Loader2, MessageSquarePlus, Save, Trash2, Upload, X } from 'lucide-react';

import { PendingAccess, PendingDocument, PendingDocumentsResponse, PendingRow } from '@/lib/types/pendientes';
import { createPendingFolder, createPendingFollowUp, deletePendingRecord, getPendingDocuments, updatePendingRecord, uploadPendingDocument } from '@/modules/pendientes/service';
import { agentsForPromotoria, PendingAgentSelect } from './PendingAgentSelect';

type PendingSourceKey = 'emision-servicios' | 'siniestros';
type DetailTab = 'detalle' | 'expediente';

const EMISION_STATUS_OPTIONS = [
    { value: 'En cotización', description: 'La solicitud se está cotizando y todavía no existe una propuesta final.' },
    { value: 'En negociación', description: 'La propuesta está siendo revisada o negociada con el asegurado.' },
    { value: 'Recabando información', description: 'Faltan datos o documentos necesarios para continuar el trámite.' },
    { value: 'Pendiente Taiico', description: 'La siguiente acción corresponde al equipo de Taiico.' },
    { value: 'Pendiente Asegurado', description: 'Se espera información, documentos o una decisión del asegurado.' },
    { value: 'Pendiente MetLife', description: 'El trámite está en revisión o espera de respuesta por parte de MetLife.' },
    { value: 'Reingresado MetLife', description: 'El trámite fue enviado nuevamente a MetLife para continuar su revisión.' },
    { value: 'Concluido', description: 'El trámite terminó y no requiere acciones adicionales.' },
] as const;

const SINIESTROS_STATUS_OPTIONS = [
    { value: 'En Proceso', description: 'El siniestro continúa en revisión o gestión.' },
    { value: 'Pagado', description: 'La aseguradora realizó el pago correspondiente.' },
    { value: 'Rechazado', description: 'La aseguradora rechazó el siniestro o la reclamación.' },
    { value: 'Suspendido', description: 'La gestión del siniestro está detenida temporalmente.' },
] as const;

interface PendingHistoryModalProps {
    row: PendingRow | null;
    source: PendingSourceKey;
    onUpdated: (row: PendingRow) => void;
    onDeleted: (row: PendingRow) => void | Promise<void>;
    onClose: () => void;
    access: PendingAccess;
}

export function PendingHistoryModal({ row, source, onUpdated, onDeleted, onClose, access }: PendingHistoryModalProps) {
    const canOperate = access.can_operate;
    const [tab, setTab] = useState<DetailTab>('detalle');
    const [documents, setDocuments] = useState<PendingDocumentsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [creatingFolder, setCreatingFolder] = useState(false);
    const [uploadingName, setUploadingName] = useState<string | null>(null);
    const [additionalName, setAdditionalName] = useState('');
    const [showFollowUp, setShowFollowUp] = useState(false);
    const [followUpComment, setFollowUpComment] = useState('');
    const [savingFollowUp, setSavingFollowUp] = useState(false);
    const [detailValues, setDetailValues] = useState<Record<string, string>>(() => editableDetailValues(row?.summary || {}));
    const [dirtyDetailFields, setDirtyDetailFields] = useState<Set<string>>(() => new Set());
    const [savingDetails, setSavingDetails] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [folderNotice, setFolderNotice] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!successMessage) return;
        const timeout = window.setTimeout(() => setSuccessMessage(null), 3000);
        return () => window.clearTimeout(timeout);
    }, [successMessage]);

    const openExpediente = async () => {
        setTab('expediente');
        if (!row || documents || loading) return;
        setLoading(true);
        setError(null);
        try {
            setDocuments(await getPendingDocuments(source, row.source_row));
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible consultar el expediente.');
        } finally {
            setLoading(false);
        }
    };

    const completedRequirements = useMemo(() => {
        const names = new Set((documents?.documents || []).map((document) => normalizeDocumentName(document.name)));
        return new Set((documents?.required_documents || []).filter((requirement) => names.has(normalizeDocumentName(requirement))));
    }, [documents]);

    if (!row) return null;

    const createFolder = async () => {
        setCreatingFolder(true);
        setError(null);
        try {
            const response = await createPendingFolder(source, row.source_row);
            setDocuments((current) => current ? { ...current, row: response.row, folder_missing: false } : current);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible crear la carpeta.');
        } finally {
            setCreatingFolder(false);
        }
    };

    const upload = async (documentName: string, file: globalThis.File) => {
        setUploadingName(documentName);
        setError(null);
        try {
            const response = await uploadPendingDocument(source, row.source_row, documentName, file);
            setDocuments((current) => current ? {
                ...current,
                row: response.row,
                folder_missing: false,
                documents: [...current.documents.filter((item) => item.id !== response.document.id), response.document],
            } : current);
            onUpdated(response.row);
            setAdditionalName('');
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible cargar el archivo.');
        } finally {
            setUploadingName(null);
        }
    };

    const folderUrl = documents?.row.folder_url || row.folder_url;

    const saveFollowUp = async () => {
        if (!followUpComment.trim()) return;
        setSavingFollowUp(true);
        setError(null);
        try {
            const response = await createPendingFollowUp(source, row.source_row, followUpComment);
            onUpdated(response.row);
            setFollowUpComment('');
            setShowFollowUp(false);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible guardar el seguimiento.');
        } finally {
            setSavingFollowUp(false);
        }
    };

    const saveDetails = async () => {
        const changedValues = Object.fromEntries(
            [...dirtyDetailFields]
                .filter((key) => detailValues[key] !== comparableDetailValue(key, row.summary[key] || ''))
                .map((key) => [key, detailValues[key]]),
        );
        if (Object.keys(changedValues).length === 0) return;
        setSavingDetails(true);
        setError(null);
        setFolderNotice(null);
        setSuccessMessage(null);
        try {
            const response = await updatePendingRecord(source, row.source_row, changedValues);
            setDetailValues(editableDetailValues(response.row.summary));
            setDirtyDetailFields(new Set());
            setFolderNotice(response.folder_warning || null);
            setSuccessMessage('Pendiente actualizado correctamente.');
            setDocuments(null);
            onUpdated(response.row);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible guardar los cambios.');
        } finally {
            setSavingDetails(false);
        }
    };

    const deleteRecord = async () => {
        const confirmed = window.confirm(
            '¿Eliminar este registro de pendiente? Esta acción quitará la fila de la tabla. '
            + 'La carpeta del expediente y sus documentos se conservarán.',
        );
        if (!confirmed) return;
        setDeleting(true);
        setError(null);
        try {
            await deletePendingRecord(source, row.source_row);
            await onDeleted(row);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible eliminar el pendiente.');
            setDeleting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
            {successMessage && (
                <div role="status" className="fixed right-4 top-4 z-[60] flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800 shadow-lg">
                    <CheckCircle2 className="h-5 w-5" />
                    {successMessage}
                </div>
            )}
            <div className="max-h-[92vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-xl" onMouseDown={(event) => event.stopPropagation()}>
                <div className="flex items-start justify-between border-b px-6 py-4">
                    <div>
                        <h2 className="text-xl font-semibold text-gray-900">Detalle del pendiente</h2>
                        <p className="mt-1 text-sm text-gray-500">Fila {row.source_row} · RFC {row.summary.RFC || 'no registrado'}</p>
                    </div>
                    <button type="button" onClick={onClose} className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600" aria-label="Cerrar detalle"><X className="h-6 w-6" /></button>
                </div>

                <div className="flex items-center justify-between gap-3 border-b px-6">
                    <div className="flex">
                        <TabButton active={tab === 'detalle'} onClick={() => setTab('detalle')}>Detalle e historial</TabButton>
                        <TabButton active={tab === 'expediente'} onClick={openExpediente}>Integración del expediente</TabButton>
                    </div>
                    {canOperate && (
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={deleteRecord}
                                disabled={deleting}
                                className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                            >
                                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                                <span className="hidden sm:inline">Eliminar registro</span>
                            </button>
                            <button type="button" onClick={() => setShowFollowUp((current) => !current)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                                <MessageSquarePlus className="h-4 w-4" /> Seguimiento
                            </button>
                        </div>
                    )}
                </div>

                <div className="max-h-[calc(92vh-142px)] overflow-y-auto p-6">
                    {showFollowUp && (
                        <div className="mb-5 rounded-xl border border-blue-200 bg-blue-50 p-4">
                            <label className="text-sm font-semibold text-blue-950" htmlFor="pending-follow-up">Comentario de seguimiento</label>
                            <textarea id="pending-follow-up" autoFocus value={followUpComment} onChange={(event) => setFollowUpComment(event.target.value)} rows={3} maxLength={5000} placeholder="Ej. En espera de firma del cliente" className="mt-2 w-full resize-y rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                            <div className="mt-3 flex justify-end gap-2">
                                <button type="button" onClick={() => { setShowFollowUp(false); setFollowUpComment(''); }} disabled={savingFollowUp} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white">Cancelar</button>
                                <button type="button" onClick={saveFollowUp} disabled={savingFollowUp || !followUpComment.trim()} className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                                    {savingFollowUp && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Guardar seguimiento
                                </button>
                            </div>
                        </div>
                    )}
                    {error && <div className="mb-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
                    {folderNotice && <div className="mb-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{folderNotice}</div>}
                    {tab === 'detalle' ? (
                        <DetailTabContent
                            row={row}
                            source={source}
                            values={detailValues}
                            saving={savingDetails}
                            dirtyFields={dirtyDetailFields}
                            onChange={(label, value) => {
                                setDetailValues((current) => applyDerivedDayValue(current, label, value));
                                setDirtyDetailFields((current) => {
                                    const next = new Set(current).add(label);
                                    const derivedLabel = derivedFieldLabel(detailValues, label);
                                    if (derivedLabel) next.add(derivedLabel);
                                    return next;
                                });
                            }}
                            onSave={saveDetails}
                            access={access}
                        />
                    ) : loading ? (
                        <div className="flex items-center justify-center py-16 text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Consultando Drive...</div>
                    ) : (
                        <div>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-900">Expediente {row.summary.RFC || ''}</h3>
                                    <p className="text-sm text-slate-500">Cada registro tiene una carpeta propia, identificada por RFC, fecha, hora y tipo de solicitud.</p>
                                </div>
                                {folderUrl && <a href={folderUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-slate-50">Abrir carpeta <ExternalLink className="h-4 w-4" /></a>}
                            </div>

                            {documents?.folder_missing && !row.summary.RFC ? (
                                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
                                    Este pendiente todavía no tiene RFC. Agrégalo en “Detalle e historial” para crear automáticamente su carpeta.
                                </div>
                            ) : documents?.folder_missing ? (
                                <div className="mt-5 rounded-xl border border-dashed border-slate-300 p-8 text-center">
                                    <FolderOpen className="mx-auto h-9 w-9 text-slate-400" />
                                    <p className="mt-2 text-sm text-slate-600">Este registro todavía no tiene carpeta de expediente.</p>
                                    {canOperate && <button type="button" onClick={createFolder} disabled={creatingFolder} className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                                        {creatingFolder && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Crear carpeta {row.summary.RFC}
                                    </button>}
                                </div>
                            ) : documents ? (
                                <>
                                    {documents.required_documents.length > 0 ? (
                                        <div className="mt-5 space-y-2">
                                            <div className="flex items-center justify-between"><h4 className="font-semibold text-slate-900">Documentos requeridos</h4><span className="text-sm text-slate-500">{completedRequirements.size} de {documents.required_documents.length}</span></div>
                                            {documents.required_documents.map((requirement) => {
                                                const complete = completedRequirements.has(requirement);
                                                return (
                                                    <div key={requirement} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 p-3">
                                                        <CheckCircle2 className={`h-5 w-5 shrink-0 ${complete ? 'text-emerald-600' : 'text-slate-300'}`} />
                                                        <span className="min-w-0 flex-1 text-sm font-medium text-slate-800">{requirement}</span>
                                                        {canOperate && <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700">
                                                            {uploadingName === requirement ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                                                            {complete ? 'Cargar nueva versión' : 'Cargar'}
                                                            <input type="file" className="hidden" disabled={Boolean(uploadingName)} onChange={(event) => handleFileSelection(event, requirement, upload)} />
                                                        </label>}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-800">Este tipo de pendiente todavía no tiene una lista documental obligatoria; puedes cargar archivos adicionales abajo.</div>
                                    )}

                                    {canOperate && <div className="mt-6 rounded-xl border border-slate-200 p-4">
                                        <h4 className="font-semibold text-slate-900">Agregar documento adicional</h4>
                                        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                                            <input value={additionalName} onChange={(event) => setAdditionalName(event.target.value)} placeholder="Nombre del documento" className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-black placeholder:text-slate-400" />
                                            <label className={`inline-flex items-center justify-center gap-1 rounded-lg px-4 py-2 text-sm font-semibold text-white ${additionalName.trim() ? 'cursor-pointer bg-blue-600 hover:bg-blue-700' : 'cursor-not-allowed bg-slate-300'}`}>
                                                <Upload className="h-4 w-4" /> Seleccionar archivo
                                                <input type="file" className="hidden" disabled={!additionalName.trim() || Boolean(uploadingName)} onChange={(event) => handleFileSelection(event, additionalName, upload)} />
                                            </label>
                                        </div>
                                    </div>}

                                    <DocumentList documents={documents.documents} />
                                </>
                            ) : null}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function DetailTabContent({
    row,
    source,
    values,
    saving,
    dirtyFields,
    onChange,
    onSave,
    access,
}: {
    row: PendingRow;
    source: PendingSourceKey;
    values: Record<string, string>;
    saving: boolean;
    dirtyFields: Set<string>;
    onChange: (label: string, value: string) => void;
    onSave: () => void;
    access: PendingAccess;
}) {
    const canOperate = access.can_operate;
    const promotoriaLabel = Object.keys(values).find(
        (label) => normalizeFieldLabel(label) === 'promotoria',
    );
    const rfcAgenteLabel = Object.keys(values).find(
        (label) => normalizeFieldLabel(label) === 'rfc agente',
    );
    const responsableLabel = Object.keys(values).find(
        (label) => normalizeFieldLabel(label) === 'responsable',
    );
    const selectedPromotoria = promotoriaLabel ? values[promotoriaLabel] : '';
    const selectedResponsable = responsableLabel ? values[responsableLabel].trim().toLocaleLowerCase('es-MX') : '';
    const responsibleIsValid = (access.admins || []).some((admin) => admin.email === selectedResponsable);
    const hasChanges = [...dirtyFields].some(
        (key) => values[key] !== comparableDetailValue(key, row.summary[key] || ''),
    );
    return <>
        <div className="rounded-lg bg-gray-50 p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {Object.entries(values)
                    .filter(([label]) => label.trim().toLocaleLowerCase('es-MX') !== 'fecha hoy')
                    .map(([label, value]) => {
                        const derived = isDerivedDayField(label);
                        const automaticDate = isAutomaticStartDateField(source, label);
                        const normalizedLabel = normalizeFieldLabel(label);
                        return (
                            <label key={label} className="block">
                                <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</span>
                                {normalizedLabel === 'promotoria' ? (
                                    <select
                                        required
                                        disabled={!canOperate || access.promotorias.length === 1}
                                        value={value}
                                        onChange={(event) => {
                                            const nextPromotoria = event.target.value;
                                            onChange(label, nextPromotoria);
                                            if (
                                                rfcAgenteLabel
                                                && !agentsForPromotoria(access.agents, nextPromotoria)
                                                    .some((agent) => agent.rfc === values[rfcAgenteLabel])
                                            ) {
                                                onChange(rfcAgenteLabel, '');
                                            }
                                        }}
                                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                                    >
                                        <option value="">Seleccionar...</option>
                                        {access.promotorias.map((promotoria) => (
                                            <option key={promotoria} value={promotoria}>{promotoria}</option>
                                        ))}
                                    </select>
                                ) : normalizedLabel === 'rfc agente' ? (
                                    <PendingAgentSelect
                                        agents={access.agents}
                                        promotoria={selectedPromotoria}
                                        value={value}
                                        onChange={(nextValue) => onChange(label, nextValue)}
                                        disabled={!canOperate}
                                        required={false}
                                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                                    />
                                ) : normalizedLabel === 'responsable' ? (
                                    <div className="mt-1">
                                        <select
                                            required
                                            disabled={!canOperate}
                                            value={(access.admins || []).some((admin) => admin.email === value.trim().toLocaleLowerCase('es-MX')) ? value.trim().toLocaleLowerCase('es-MX') : ''}
                                            onChange={(event) => onChange(label, event.target.value)}
                                            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                                        >
                                            <option value="">Seleccionar administrador...</option>
                                            {(access.admins || []).map((admin) => (
                                                <option key={admin.email} value={admin.email}>{admin.label}</option>
                                            ))}
                                        </select>
                                        {value && !(access.admins || []).some((admin) => admin.email === value.trim().toLocaleLowerCase('es-MX')) && (
                                            <p className="mt-1 text-xs text-amber-700">Valor histórico: {value}. Selecciona un usuario Admin para guardar cambios.</p>
                                        )}
                                    </div>
                                ) : source === 'emision-servicios' && normalizedLabel === 'estatus actual' ? (
                                    <PendingStatusSelect
                                        value={value}
                                        onChange={(nextValue) => onChange(label, nextValue)}
                                        disabled={!canOperate}
                                        options={EMISION_STATUS_OPTIONS}
                                        ariaLabel="Estatus actual"
                                    />
                                ) : source === 'siniestros' && normalizedLabel === 'estatus' ? (
                                    <PendingStatusSelect
                                        value={value}
                                        onChange={(nextValue) => onChange(label, nextValue)}
                                        disabled={!canOperate}
                                        options={SINIESTROS_STATUS_OPTIONS}
                                        ariaLabel="Estatus"
                                    />
                                ) : source === 'emision-servicios' && normalizedLabel === 'tipo de tramite' ? (
                                    <div className="mt-1">
                                        <select
                                            value={value === 'Emisión' || value === 'Servicios' ? value : ''}
                                            disabled={!canOperate}
                                            onChange={(event) => onChange(label, event.target.value)}
                                            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                                        >
                                            <option value="" disabled>Seleccionar...</option>
                                            <option value="Emisión">Emisión</option>
                                            <option value="Servicios">Servicios</option>
                                        </select>
                                        {value && value !== 'Emisión' && value !== 'Servicios' && (
                                            <p className="mt-1 text-xs text-amber-700">Valor histórico: selecciona Emisión o Servicios para actualizarlo.</p>
                                        )}
                                    </div>
                                ) : label.toLocaleLowerCase('es-MX').includes('comentario') ? (
                                    <textarea disabled={!canOperate} value={value} onChange={(event) => onChange(label, event.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100" />
                                ) : (
                                    <input
                                        type={isDateField(label) && !automaticDate ? 'date' : 'text'}
                                        inputMode={normalizedLabel === 'monto' ? 'decimal' : undefined}
                                        value={value}
                                        placeholder={normalizedLabel === 'monto' ? '0.00 MXN' : undefined}
                                        readOnly={derived || automaticDate}
                                        disabled={!canOperate}
                                        onChange={(event) => onChange(label, label === 'RFC' ? event.target.value.toUpperCase() : event.target.value)}
                                        title={automaticDate ? 'Esta fecha se asigna automáticamente al crear el registro.' : undefined}
                                        className={`mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-gray-900 outline-none ${derived || automaticDate ? 'cursor-not-allowed bg-slate-100' : 'bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-100'}`}
                                    />
                                )}
                            </label>
                        );
                    })}
            </div>
            {canOperate && <div className="mt-4 flex justify-end">
                <button type="button" onClick={onSave} disabled={saving || !hasChanges || !responsibleIsValid} className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                    {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Guardar cambios
                </button>
            </div>}
        </div>
        <h3 className="mb-3 mt-6 text-lg font-semibold text-gray-900">Historial de actualizaciones</h3>
        {row.history.length === 0 ? <p className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">No hay actualizaciones registradas.</p> : (
            <ol className="space-y-3 border-l-2 border-blue-200 pl-5">
                {[...row.history].reverse().map((entry, index) => <li key={`${entry.date}-${index}`} className="relative rounded-lg border bg-white p-4 shadow-sm"><span className="absolute -left-[1.72rem] top-5 h-3 w-3 rounded-full bg-blue-600 ring-4 ring-white" /><p className="text-sm font-semibold text-blue-700">{formatHistoryDate(entry.date)}</p><p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{entry.update}</p></li>)}
            </ol>
        )}
    </>;
}

function PendingStatusSelect({
    value,
    onChange,
    disabled,
    options,
    ariaLabel,
}: {
    value: string;
    onChange: (value: string) => void;
    disabled: boolean;
    options: readonly { value: string; description: string }[];
    ariaLabel: string;
}) {
    const [open, setOpen] = useState(false);
    const [hoveredDescription, setHoveredDescription] = useState('');
    const containerRef = useRef<HTMLDivElement>(null);
    const selectedOption = options.find((option) => option.value === value);

    useEffect(() => {
        if (!open) return;
        const closeOnOutsideClick = (event: MouseEvent) => {
            if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
        };
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setOpen(false);
        };
        document.addEventListener('mousedown', closeOnOutsideClick);
        document.addEventListener('keydown', closeOnEscape);
        return () => {
            document.removeEventListener('mousedown', closeOnOutsideClick);
            document.removeEventListener('keydown', closeOnEscape);
        };
    }, [open]);

    return (
        <div ref={containerRef} className="relative mt-1">
            <button
                type="button"
                aria-haspopup="listbox"
                aria-expanded={open}
                disabled={disabled}
                onClick={() => setOpen((current) => !current)}
                className="flex w-full items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
            >
                <span className={value ? '' : 'text-slate-400'}>{value || 'Seleccionar...'}</span>
                <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>
            {open && (
                <div className="absolute z-30 mt-1 w-full min-w-72 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl">
                    <div role="listbox" aria-label={ariaLabel} className="max-h-64 overflow-y-auto py-1">
                        {options.map((option) => (
                            <button
                                key={option.value}
                                type="button"
                                role="option"
                                aria-selected={option.value === value}
                                title={option.description}
                                onMouseEnter={() => setHoveredDescription(option.description)}
                                onFocus={() => setHoveredDescription(option.description)}
                                onClick={() => {
                                    onChange(option.value);
                                    setOpen(false);
                                    setHoveredDescription('');
                                }}
                                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-slate-800 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none"
                            >
                                <span>{option.value}</span>
                                {option.value === value && <Check className="h-4 w-4 shrink-0 text-blue-600" />}
                            </button>
                        ))}
                    </div>
                    <div aria-live="polite" className="min-h-14 border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
                        {hoveredDescription || selectedOption?.description || 'Pasa el cursor sobre una opción para consultar su descripción.'}
                    </div>
                </div>
            )}
            {value && !selectedOption && (
                <p className="mt-1 text-xs text-amber-700">Estatus histórico: selecciona una opción vigente para actualizarlo.</p>
            )}
        </div>
    );
}

function DocumentList({ documents }: { documents: PendingDocument[] }) {
    if (documents.length === 0) return <div className="mt-5 rounded-lg bg-slate-50 p-5 text-center text-sm text-slate-500">La carpeta todavía no contiene documentos.</div>;
    return <div className="mt-5 divide-y divide-slate-100 rounded-xl border border-slate-200">
        {documents.map((document) => <a key={document.id} href={document.webViewLink} target="_blank" rel="noreferrer" className="flex items-center gap-3 p-3 hover:bg-slate-50"><File className="h-5 w-5 shrink-0 text-blue-600" /><div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-800">{document.name}</div>{document.modifiedTime && <div className="text-xs text-slate-500">Actualizado {new Date(document.modifiedTime).toLocaleDateString('es-MX')}</div>}</div><ExternalLink className="h-4 w-4 text-slate-400" /></a>)}
    </div>;
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
    return <button type="button" onClick={onClick} className={`border-b-2 px-4 py-3 text-sm font-semibold ${active ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>{children}</button>;
}

function normalizeDocumentName(name: string): string {
    return name.replace(/\.[^.]+$/, '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim().toLocaleLowerCase('es-MX');
}

export function formatHistoryDate(value: string): string {
    const text = value.trim();
    const iso = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (iso) return `${iso[3].padStart(2, '0')} - ${MONTH_NAMES[Number(iso[2]) - 1]}`;
    const numeric = text.match(/^(\d{1,2})[/-](\d{1,2})[/-]\d{2,4}$/);
    if (numeric) return `${numeric[1].padStart(2, '0')} - ${MONTH_NAMES[Number(numeric[2]) - 1]}`;
    const named = text.match(/^(\d{1,2})\s*-\s*([A-Za-zÁÉÍÓÚáéíóú]{3})/);
    if (named) return `${named[1].padStart(2, '0')} - ${named[2][0].toUpperCase()}${named[2].slice(1).toLowerCase()}`;
    return text;
}

const MONTH_NAMES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

const DATE_TO_DAY_FIELD: Record<string, string> = {
    'fecha inicio': 'dias transcurridos',
    'fecha ingreso en la aseguradora': 'dias en la aseguradora',
    'fecha de registro de siniestro': 'dias desde registro del siniestro',
    'fecha de envio a la aseguradora': 'dias cumplidos en la aseguradora',
    'fecha de envio': 'dias cumplidos',
};

const DERIVED_DAY_FIELDS = new Set(Object.values(DATE_TO_DAY_FIELD));

function normalizeFieldLabel(value: string): string {
    return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim().toLocaleLowerCase('es-MX');
}

function isDateField(label: string): boolean {
    const normalized = normalizeFieldLabel(label);
    return normalized in DATE_TO_DAY_FIELD || normalized === 'recordatorio futuro';
}

function isDerivedDayField(label: string): boolean {
    return DERIVED_DAY_FIELDS.has(normalizeFieldLabel(label));
}

function isAutomaticStartDateField(source: PendingSourceKey, label: string): boolean {
    const normalizedLabel = normalizeFieldLabel(label);
    return source === 'emision-servicios'
        ? normalizedLabel === 'fecha inicio'
        : normalizedLabel === 'fecha de registro de siniestro';
}

function isAutomaticallyAssignedDateField(label: string): boolean {
    const normalizedLabel = normalizeFieldLabel(label);
    return normalizedLabel === 'fecha inicio' || normalizedLabel === 'fecha de registro de siniestro';
}

function toDateInputValue(value: string): string {
    const text = value.trim();
    const iso = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (iso) return `${iso[1]}-${iso[2].padStart(2, '0')}-${iso[3].padStart(2, '0')}`;
    const dayFirst = text.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$/);
    if (dayFirst) {
        const year = dayFirst[3].length === 2 ? `20${dayFirst[3]}` : dayFirst[3];
        return `${year}-${dayFirst[2].padStart(2, '0')}-${dayFirst[1].padStart(2, '0')}`;
    }
    if (/^\d+(?:\.0+)?$/.test(text)) {
        const serial = Number(text);
        const date = new Date(Date.UTC(1899, 11, 30) + serial * 86_400_000);
        return Number.isNaN(date.getTime()) ? '' : date.toISOString().slice(0, 10);
    }
    return '';
}

function comparableDetailValue(label: string, value: string): string {
    return isDateField(label) && !isAutomaticallyAssignedDateField(label) ? toDateInputValue(value) : value;
}

function editableDetailValues(summary: Record<string, string>): Record<string, string> {
    return Object.fromEntries(
        Object.entries(summary).map(([label, value]) => [label, comparableDetailValue(label, value)]),
    );
}

function mexicoCityTodayParts(): { year: number; month: number; day: number } {
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Mexico_City',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).formatToParts(new Date());
    const value = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
    return { year: value('year'), month: value('month'), day: value('day') };
}

function daysSince(value: string): string {
    const iso = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!iso) return '';
    const today = mexicoCityTodayParts();
    const current = Date.UTC(today.year, today.month - 1, today.day);
    const start = Date.UTC(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
    return String(Math.max(0, Math.floor((current - start) / 86_400_000)));
}

function applyDerivedDayValue(
    values: Record<string, string>,
    changedLabel: string,
    value: string,
): Record<string, string> {
    const next = { ...values, [changedLabel]: value };
    const targetNormalized = DATE_TO_DAY_FIELD[normalizeFieldLabel(changedLabel)];
    if (!targetNormalized) return next;
    const targetLabel = Object.keys(values).find((label) => normalizeFieldLabel(label) === targetNormalized);
    if (targetLabel) next[targetLabel] = daysSince(value);
    return next;
}

function derivedFieldLabel(values: Record<string, string>, changedLabel: string): string | null {
    const targetNormalized = DATE_TO_DAY_FIELD[normalizeFieldLabel(changedLabel)];
    if (!targetNormalized) return null;
    return Object.keys(values).find((label) => normalizeFieldLabel(label) === targetNormalized) || null;
}

function handleFileSelection(event: ChangeEvent<HTMLInputElement>, documentName: string, upload: (name: string, file: globalThis.File) => Promise<void>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) void upload(documentName, file);
}
