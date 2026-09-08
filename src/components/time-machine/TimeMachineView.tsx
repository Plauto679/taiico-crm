'use client';

import { useMemo, useState } from 'react';
import { ArchiveRestore, CheckCircle2, Clock3, ExternalLink, HardDrive, ShieldCheck, X } from 'lucide-react';
import { BackupSource, RestorePoint, TimeMachineCatalog, restoreTimeMachineBackup } from '@/modules/time-machine/service';

function formatBytes(value: number): string {
    if (!value) return 'Tamaño no disponible';
    if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function displayDate(value?: string | null): string {
    if (!value) return 'Fecha no disponible';
    const parts = value.slice(0, 10).split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
}

export function TimeMachineView({ initialCatalog }: { initialCatalog: TimeMachineCatalog }) {
    const [catalog, setCatalog] = useState(initialCatalog);
    const [sourceKey, setSourceKey] = useState(
        initialCatalog.sources.find((source) => source.versions.length)?.key
        || initialCatalog.sources[0]?.key
        || '',
    );
    const [candidate, setCandidate] = useState<{ source: BackupSource; version: RestorePoint } | null>(null);
    const [confirmation, setConfirmation] = useState('');
    const [restoring, setRestoring] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const selectedSource = useMemo(
        () => catalog.sources.find((source) => source.key === sourceKey) || catalog.sources[0],
        [catalog.sources, sourceKey],
    );

    async function restore() {
        if (!candidate || confirmation.trim().toUpperCase() !== 'RESTAURAR' || restoring) return;
        setRestoring(true);
        setError('');
        setSuccess('');
        try {
            const result = await restoreTimeMachineBackup({
                source_key: candidate.source.key,
                backup_file_id: candidate.version.id,
                confirmation,
            });
            setSuccess(
                `${result.source_name} fue restaurada desde ${displayDate(candidate.version.backup_date)}. `
                + 'También se creó un respaldo del estado que existía antes de la restauración.',
            );
            setCatalog((current) => ({ ...current }));
            setCandidate(null);
            setConfirmation('');
        } catch (restoreError) {
            setError(restoreError instanceof Error ? restoreError.message : 'No fue posible restaurar la base');
        } finally {
            setRestoring(false);
        }
    }

    return (
        <div className="flex h-full min-h-0 flex-col gap-5 p-4 sm:p-8">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                    <div className="flex items-center gap-3 text-white">
                        <ArchiveRestore className="h-8 w-8" />
                        <h1 className="text-3xl font-bold">Time Machine</h1>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-blue-100 sm:text-base">
                        Consulta los respaldos diarios y recupera una base conservando sus enlaces e integraciones actuales.
                    </p>
                </div>
                <a
                    href={catalog.root_folder_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/30 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
                >
                    Abrir respaldos en Drive <ExternalLink className="h-4 w-4" />
                </a>
            </div>

            {success && (
                <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                    <span>{success}</span>
                </div>
            )}
            {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

            <div className="grid min-h-0 flex-1 overflow-hidden rounded-2xl bg-white shadow-xl lg:grid-cols-[22rem_minmax(0,1fr)]">
                <section className="min-h-0 overflow-y-auto border-b border-slate-200 bg-slate-50 p-4 lg:border-b-0 lg:border-r">
                    <h2 className="px-2 text-xs font-bold uppercase tracking-wider text-slate-500">Bases respaldadas</h2>
                    <div className="mt-3 space-y-2">
                        {catalog.sources.map((source) => (
                            <button
                                type="button"
                                key={source.key}
                                onClick={() => { setSourceKey(source.key); setError(''); setSuccess(''); }}
                                className={`w-full rounded-xl border p-3 text-left transition ${source.key === selectedSource?.key ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-transparent bg-white hover:border-slate-200'}`}
                            >
                                <div className="flex items-start gap-3">
                                    <HardDrive className={`mt-0.5 h-5 w-5 shrink-0 ${source.key === selectedSource?.key ? 'text-blue-600' : 'text-slate-400'}`} />
                                    <div className="min-w-0">
                                        <p className="font-semibold text-slate-800">{source.name}</p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            {source.version_count} {source.version_count === 1 ? 'versión' : 'versiones'}
                                            {source.latest_backup_date ? ` · Última ${displayDate(source.latest_backup_date)}` : ''}
                                        </p>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                </section>

                <section className="min-h-0 overflow-y-auto p-5 sm:p-7">
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">{selectedSource?.name || 'Base de datos'}</h2>
                            <p className="mt-1 text-sm text-slate-500">Selecciona el punto al que deseas regresar.</p>
                        </div>
                        <div className="hidden items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 sm:flex">
                            <ShieldCheck className="h-4 w-4" /> Respaldo previo automático
                        </div>
                    </div>

                    <div className="mt-5 space-y-3">
                        {!selectedSource?.versions.length && (
                            <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-500">
                                Todavía no hay respaldos disponibles para esta base.
                            </div>
                        )}
                        {selectedSource?.versions.map((version) => (
                            <article key={version.id} className="flex flex-col gap-4 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
                                <div className="flex min-w-0 items-start gap-3">
                                    <Clock3 className="mt-1 h-5 w-5 shrink-0 text-blue-600" />
                                    <div className="min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <h3 className="font-bold text-slate-900">{displayDate(version.backup_date)}</h3>
                                            {version.reason === 'pre_restore' && (
                                                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Previo a restauración</span>
                                            )}
                                        </div>
                                        <p className="mt-1 truncate text-sm text-slate-500" title={version.name}>{version.name}</p>
                                        <p className="mt-1 text-xs text-slate-400">{formatBytes(version.size)}</p>
                                    </div>
                                </div>
                                <div className="flex shrink-0 gap-2">
                                    {version.web_view_link && (
                                        <a href={version.web_view_link} target="_blank" rel="noreferrer" className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50">Ver</a>
                                    )}
                                    {catalog.can_restore && (
                                        <button type="button" onClick={() => { setCandidate({ source: selectedSource, version }); setConfirmation(''); setError(''); }} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                                            Restaurar
                                        </button>
                                    )}
                                </div>
                            </article>
                        ))}
                    </div>
                </section>
            </div>

            {candidate && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4">
                    <div role="dialog" aria-modal="true" className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
                        <div className="flex items-start justify-between border-b p-5">
                            <div>
                                <h2 className="text-xl font-bold text-slate-900">Confirmar restauración</h2>
                                <p className="mt-1 text-sm text-slate-500">Esta operación reemplazará la información vigente.</p>
                            </div>
                            <button type="button" onClick={() => setCandidate(null)} disabled={restoring} className="rounded-full p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
                        </div>
                        <div className="space-y-4 p-5">
                            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                                Restaurarás <strong>{candidate.source.name}</strong> al respaldo del <strong>{displayDate(candidate.version.backup_date)}</strong>. Antes se guardará automáticamente una copia del estado actual para poder deshacer el cambio.
                            </div>
                            <label className="block text-sm font-semibold text-slate-700">
                                Escribe <strong>RESTAURAR</strong> para continuar
                                <input
                                    autoFocus
                                    value={confirmation}
                                    onChange={(event) => setConfirmation(event.target.value)}
                                    disabled={restoring}
                                    className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 uppercase outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                                />
                            </label>
                        </div>
                        <div className="flex justify-end gap-3 border-t p-5">
                            <button type="button" onClick={() => setCandidate(null)} disabled={restoring} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">Cancelar</button>
                            <button type="button" onClick={restore} disabled={restoring || confirmation.trim().toUpperCase() !== 'RESTAURAR'} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-40">
                                {restoring ? 'Restaurando...' : 'Restaurar versión'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
