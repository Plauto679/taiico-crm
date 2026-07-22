'use client';

import { ChangeEvent, useMemo, useState } from 'react';
import { CheckCircle2, ExternalLink, File, FolderOpen, Loader2, MessageSquarePlus, Upload, X } from 'lucide-react';

import { PendingDocument, PendingDocumentsResponse, PendingRow } from '@/lib/types/pendientes';
import { createPendingFolder, createPendingFollowUp, getPendingDocuments, uploadPendingDocument } from '@/modules/pendientes/service';

type PendingSourceKey = 'emision-servicios' | 'siniestros';
type DetailTab = 'detalle' | 'expediente';

interface PendingHistoryModalProps {
    row: PendingRow | null;
    source: PendingSourceKey;
    onUpdated: (row: PendingRow) => void;
    onClose: () => void;
}

export function PendingHistoryModal({ row, source, onUpdated, onClose }: PendingHistoryModalProps) {
    const [tab, setTab] = useState<DetailTab>('detalle');
    const [documents, setDocuments] = useState<PendingDocumentsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [creatingFolder, setCreatingFolder] = useState(false);
    const [uploadingName, setUploadingName] = useState<string | null>(null);
    const [additionalName, setAdditionalName] = useState('');
    const [showFollowUp, setShowFollowUp] = useState(false);
    const [followUpComment, setFollowUpComment] = useState('');
    const [savingFollowUp, setSavingFollowUp] = useState(false);
    const [error, setError] = useState<string | null>(null);

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
                folder_missing: false,
                documents: [...current.documents.filter((item) => item.id !== response.document.id), response.document],
            } : current);
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

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onMouseDown={onClose}>
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
                    <button type="button" onClick={() => setShowFollowUp((current) => !current)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                        <MessageSquarePlus className="h-4 w-4" /> Seguimiento
                    </button>
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
                    {tab === 'detalle' ? (
                        <DetailTabContent row={row} />
                    ) : loading ? (
                        <div className="flex items-center justify-center py-16 text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Consultando Drive...</div>
                    ) : (
                        <div>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-900">Expediente {row.summary.RFC || ''}</h3>
                                    <p className="text-sm text-slate-500">Los archivos se guardan en la carpeta de Drive nombrada con el RFC.</p>
                                </div>
                                {folderUrl && <a href={folderUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-slate-50">Abrir carpeta <ExternalLink className="h-4 w-4" /></a>}
                            </div>

                            {documents?.folder_missing && !row.summary.RFC ? (
                                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
                                    Este registro histórico todavía no tiene RFC. Agrégalo en el archivo canónico y recarga el módulo para habilitar su carpeta y expediente.
                                </div>
                            ) : documents?.folder_missing ? (
                                <div className="mt-5 rounded-xl border border-dashed border-slate-300 p-8 text-center">
                                    <FolderOpen className="mx-auto h-9 w-9 text-slate-400" />
                                    <p className="mt-2 text-sm text-slate-600">Este registro todavía no tiene carpeta de expediente.</p>
                                    <button type="button" onClick={createFolder} disabled={creatingFolder} className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                                        {creatingFolder && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Crear carpeta {row.summary.RFC}
                                    </button>
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
                                                        <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700">
                                                            {uploadingName === requirement ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                                                            {complete ? 'Cargar nueva versión' : 'Cargar'}
                                                            <input type="file" className="hidden" disabled={Boolean(uploadingName)} onChange={(event) => handleFileSelection(event, requirement, upload)} />
                                                        </label>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-800">Este tipo de pendiente todavía no tiene una lista documental obligatoria; puedes cargar archivos adicionales abajo.</div>
                                    )}

                                    <div className="mt-6 rounded-xl border border-slate-200 p-4">
                                        <h4 className="font-semibold text-slate-900">Agregar documento adicional</h4>
                                        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                                            <input value={additionalName} onChange={(event) => setAdditionalName(event.target.value)} placeholder="Nombre del documento" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                                            <label className={`inline-flex items-center justify-center gap-1 rounded-lg px-4 py-2 text-sm font-semibold text-white ${additionalName.trim() ? 'cursor-pointer bg-blue-600 hover:bg-blue-700' : 'cursor-not-allowed bg-slate-300'}`}>
                                                <Upload className="h-4 w-4" /> Seleccionar archivo
                                                <input type="file" className="hidden" disabled={!additionalName.trim() || Boolean(uploadingName)} onChange={(event) => handleFileSelection(event, additionalName, upload)} />
                                            </label>
                                        </div>
                                    </div>

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

function DetailTabContent({ row }: { row: PendingRow }) {
    return <>
        <dl className="grid grid-cols-1 gap-4 rounded-lg bg-gray-50 p-4 sm:grid-cols-2">
            {Object.entries(row.summary).map(([label, value]) => <div key={label}><dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</dt><dd className="mt-1 text-sm text-gray-900">{value || '—'}</dd></div>)}
        </dl>
        <h3 className="mb-3 mt-6 text-lg font-semibold text-gray-900">Historial de actualizaciones</h3>
        {row.history.length === 0 ? <p className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">No hay actualizaciones registradas.</p> : (
            <ol className="space-y-3 border-l-2 border-blue-200 pl-5">
                {[...row.history].reverse().map((entry, index) => <li key={`${entry.date}-${index}`} className="relative rounded-lg border bg-white p-4 shadow-sm"><span className="absolute -left-[1.72rem] top-5 h-3 w-3 rounded-full bg-blue-600 ring-4 ring-white" /><p className="text-sm font-semibold text-blue-700">{formatHistoryDate(entry.date)}</p><p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{entry.update}</p></li>)}
            </ol>
        )}
    </>;
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

function handleFileSelection(event: ChangeEvent<HTMLInputElement>, documentName: string, upload: (name: string, file: globalThis.File) => Promise<void>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) void upload(documentName, file);
}
