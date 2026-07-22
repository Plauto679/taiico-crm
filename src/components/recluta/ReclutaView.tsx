'use client';

import { useMemo, useState } from 'react';
import {
    ExternalLink,
    File,
    FolderOpen,
    LayoutGrid,
    List,
    Loader2,
    Mail,
    Phone,
    Plus,
    Search,
    Upload,
    UserRoundSearch,
    X,
} from 'lucide-react';

import { AddReclutaModal } from '@/components/recluta/AddReclutaModal';
import { UploadReclutaModal } from '@/components/recluta/UploadReclutaModal';
import {
    ReclutaDocumentsResponse,
    ReclutaProspect,
    ReclutaSource,
} from '@/lib/types/recluta';
import {
    createReclutaFolder,
    getReclutaDocuments,
} from '@/modules/recluta/service';


interface ReclutaViewProps {
    initialSource: ReclutaSource;
}

type ViewMode = 'kanban' | 'table';

function StatusBadge({ value }: { value: string }) {
    return (
        <span className="inline-flex max-w-full rounded-full bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700 ring-1 ring-inset ring-sky-200">
            <span className="truncate">{value}</span>
        </span>
    );
}

function ProspectCard({ prospect, onClick }: { prospect: ReclutaProspect; onClick: () => void }) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md"
        >
            <div className="flex items-start justify-between gap-3">
                <h3 className="font-semibold leading-5 text-slate-900">{prospect.nombre || 'Sin nombre'}</h3>
                {prospect.folder_id && <FolderOpen className="h-4 w-4 shrink-0 text-emerald-600" />}
            </div>
            <div className="mt-3"><StatusBadge value={prospect.estatus} /></div>
            <dl className="mt-3 space-y-1 text-xs text-slate-500">
                {prospect.rfc && <div className="truncate">RFC: {prospect.rfc}</div>}
                {prospect.correo && <div className="truncate">{prospect.correo}</div>}
                {prospect.telefono && <div className="truncate">{prospect.telefono}</div>}
            </dl>
        </button>
    );
}

export function ReclutaView({ initialSource }: ReclutaViewProps) {
    const [source, setSource] = useState(initialSource);
    const [mode, setMode] = useState<ViewMode>('kanban');
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState<ReclutaProspect | null>(null);
    const [documents, setDocuments] = useState<ReclutaDocumentsResponse | null>(null);
    const [loadingDocuments, setLoadingDocuments] = useState(false);
    const [creatingFolder, setCreatingFolder] = useState(false);
    const [documentError, setDocumentError] = useState<string | null>(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [creationWarning, setCreationWarning] = useState<string | null>(null);
    const [showUploadModal, setShowUploadModal] = useState(false);

    const filtered = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('es-MX');
        if (!query) return source.prospects;
        return source.prospects.filter((prospect) =>
            [prospect.nombre, prospect.rfc, prospect.correo, prospect.telefono, prospect.fase, prospect.estatus]
                .some((value) => value.toLocaleLowerCase('es-MX').includes(query))
        );
    }, [search, source.prospects]);

    const phases = useMemo(
        () => listUnique(filtered.map((prospect) => prospect.fase)),
        [filtered],
    );

    const openProspect = async (prospect: ReclutaProspect) => {
        setSelected(prospect);
        setDocuments(null);
        setDocumentError(null);
        setLoadingDocuments(true);
        try {
            setDocuments(await getReclutaDocuments(prospect.id));
        } catch (error) {
            setDocumentError(error instanceof Error ? error.message : 'No fue posible consultar los documentos.');
        } finally {
            setLoadingDocuments(false);
        }
    };

    const handleCreateFolder = async () => {
        if (!selected) return;
        setCreatingFolder(true);
        setDocumentError(null);
        try {
            const result = await createReclutaFolder(selected.id);
            setSelected(result.prospect);
            setSource((current) => ({
                ...current,
                prospects: current.prospects.map((item) =>
                    item.id === result.prospect.id ? result.prospect : item
                ),
            }));
            setDocuments(await getReclutaDocuments(selected.id));
        } catch (error) {
            setDocumentError(error instanceof Error ? error.message : 'No fue posible crear la carpeta.');
        } finally {
            setCreatingFolder(false);
        }
    };

    const handleProspectCreated = (prospect: ReclutaProspect, warning: string | null) => {
        setSource((current) => ({
            ...current,
            phases: listUnique([...current.phases, prospect.fase]),
            prospects: [...current.prospects, prospect],
        }));
        setCreationWarning(warning);
        setShowAddModal(false);
    };

    return (
        <div className="flex h-full flex-col overflow-hidden rounded-2xl bg-slate-50 shadow-xl">
            <div className="flex flex-col gap-4 border-b border-slate-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="relative w-full max-w-xl">
                    <Search className="pointer-events-none absolute left-3 top-2.5 h-5 w-5 text-slate-400" />
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Buscar por nombre, RFC, teléfono, correo, fase o estatus..."
                        className="w-full rounded-lg border border-slate-300 py-2 pl-10 pr-3 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <button type="button" onClick={() => setShowAddModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                        <Plus className="h-4 w-4" /> Agregar Recluta
                    </button>
                    <div className="flex rounded-lg border border-slate-300 p-1">
                        <button type="button" onClick={() => setMode('kanban')} className={`rounded-md p-1.5 ${mode === 'kanban' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`} title="Vista Kanban">
                            <LayoutGrid className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={() => setMode('table')} className={`rounded-md p-1.5 ${mode === 'table' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`} title="Vista de tabla">
                            <List className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>

            <div className="min-h-0 flex-1 overflow-auto p-5">
                {creationWarning && (
                    <div className="mb-4 flex items-start justify-between rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                        <span>{creationWarning}</span>
                        <button type="button" onClick={() => setCreationWarning(null)} className="ml-3 font-semibold">Cerrar</button>
                    </div>
                )}
                {source.prospects.length === 0 ? (
                    <div className="flex h-full min-h-80 items-center justify-center">
                        <div className="max-w-md text-center">
                            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                                <UserRoundSearch className="h-7 w-7" />
                            </div>
                            <h2 className="mt-4 text-lg font-semibold text-slate-900">La base de Recluta aún no tiene prospectos</h2>
                            <p className="mt-2 text-sm text-slate-500">Usa “Agregar Recluta” para registrar a la primera persona. El sistema guardará sus datos en Drive y preparará su carpeta documental.</p>
                        </div>
                    </div>
                ) : mode === 'kanban' ? (
                    <div className="flex min-w-max items-start gap-4">
                        {phases.map((phase) => {
                            const phaseProspects = filtered.filter((prospect) => prospect.fase === phase);
                            return (
                                <section key={phase} className="w-80 rounded-xl bg-slate-100 p-3">
                                    <div className="mb-3 flex items-center justify-between px-1">
                                        <h2 className="font-semibold text-slate-800">{phase}</h2>
                                        <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-500">{phaseProspects.length}</span>
                                    </div>
                                    <div className="space-y-3">
                                        {phaseProspects.map((prospect) => (
                                            <ProspectCard key={prospect.id} prospect={prospect} onClick={() => openProspect(prospect)} />
                                        ))}
                                    </div>
                                </section>
                            );
                        })}
                    </div>
                ) : (
                    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-slate-200 text-sm">
                                <thead className="sticky top-0 bg-slate-50">
                                    <tr>
                                        {source.columns.map((column) => (
                                            <th key={column} className="whitespace-nowrap px-4 py-3 text-left font-semibold text-slate-700">{column}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {filtered.map((prospect) => (
                                        <tr key={prospect.id} onClick={() => openProspect(prospect)} className="cursor-pointer hover:bg-blue-50">
                                            {source.columns.map((column) => (
                                                <td key={column} className="whitespace-nowrap px-4 py-3 text-slate-600">
                                                    {column.toLocaleLowerCase('es-MX') === 'estatus'
                                                        ? <StatusBadge value={prospect.raw[column] || 'Sin estatus'} />
                                                        : prospect.raw[column]}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>

            {selected && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={() => setSelected(null)}>
                    <div className="max-h-[88vh] w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
                        <div className="flex items-start justify-between border-b border-slate-200 p-5">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">{selected.fase}</p>
                                <h2 className="mt-1 text-xl font-bold text-slate-900">{selected.nombre || 'Sin nombre'}</h2>
                                <div className="mt-2"><StatusBadge value={selected.estatus} /></div>
                            </div>
                            <button type="button" onClick={() => setSelected(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="h-5 w-5" /></button>
                        </div>

                        <div className="max-h-[calc(88vh-120px)] overflow-y-auto p-5">
                            <div className="grid gap-3 sm:grid-cols-3">
                                <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">RFC</div><div className="mt-1 text-sm font-medium text-slate-800">{selected.rfc || 'No registrado'}</div></div>
                                <div className="rounded-lg bg-slate-50 p-3"><div className="flex items-center gap-1 text-xs text-slate-500"><Mail className="h-3.5 w-3.5" /> Correo</div><div className="mt-1 truncate text-sm font-medium text-slate-800">{selected.correo || 'No registrado'}</div></div>
                                <div className="rounded-lg bg-slate-50 p-3"><div className="flex items-center gap-1 text-xs text-slate-500"><Phone className="h-3.5 w-3.5" /> Teléfono</div><div className="mt-1 text-sm font-medium text-slate-800">{selected.telefono || 'No registrado'}</div></div>
                            </div>

                            <div className="mt-6 flex items-center justify-between">
                                <h3 className="font-semibold text-slate-900">Documentos</h3>
                                {selected.folder_url && (
                                    <div className="flex items-center gap-2">
                                        <button type="button" onClick={() => setShowUploadModal(true)} className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                                            <Upload className="h-4 w-4" /> Cargar Archivo
                                        </button>
                                        <a href={selected.folder_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-slate-50 hover:text-blue-800">Abrir carpeta <ExternalLink className="h-4 w-4" /></a>
                                    </div>
                                )}
                            </div>

                            {loadingDocuments ? (
                                <div className="flex items-center justify-center py-12 text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> Consultando Drive...</div>
                            ) : documentError ? (
                                <div className="mt-3 rounded-lg bg-red-50 p-4 text-sm text-red-700">{documentError}</div>
                            ) : documents?.folder_missing ? (
                                <div className="mt-3 rounded-xl border border-dashed border-slate-300 p-6 text-center">
                                    <FolderOpen className="mx-auto h-8 w-8 text-slate-400" />
                                    <p className="mt-2 text-sm text-slate-600">Este prospecto todavía no tiene carpeta documental.</p>
                                    <button type="button" onClick={handleCreateFolder} disabled={creatingFolder} className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                                        {creatingFolder && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                        Crear carpeta en Drive
                                    </button>
                                </div>
                            ) : documents && documents.documents.length > 0 ? (
                                <div className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
                                    {documents.documents.map((document) => (
                                        <a key={document.id} href={document.webViewLink} target="_blank" rel="noreferrer" className="flex items-center gap-3 p-3 hover:bg-slate-50">
                                            <File className="h-5 w-5 shrink-0 text-blue-600" />
                                            <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-800">{document.name}</div>{document.modifiedTime && <div className="text-xs text-slate-500">Actualizado {new Date(document.modifiedTime).toLocaleDateString('es-MX')}</div>}</div>
                                            <ExternalLink className="h-4 w-4 text-slate-400" />
                                        </a>
                                    ))}
                                </div>
                            ) : (
                                <div className="mt-3 rounded-lg bg-slate-50 p-6 text-center text-sm text-slate-500">La carpeta existe, pero todavía no contiene documentos.</div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showAddModal && (
                <AddReclutaModal
                    phases={source.phases}
                    onClose={() => setShowAddModal(false)}
                    onCreated={handleProspectCreated}
                />
            )}

            {showUploadModal && selected && (
                <UploadReclutaModal
                    prospect={selected}
                    onClose={() => setShowUploadModal(false)}
                    onUploaded={(uploadedDocument) => setDocuments((current) => current ? {
                        ...current,
                        folder_missing: false,
                        documents: [...current.documents, uploadedDocument],
                    } : current)}
                />
            )}
        </div>
    );
}

function listUnique(values: string[]): string[] {
    return Array.from(new Set(values));
}
