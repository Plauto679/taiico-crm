'use client';

import { ChangeEvent, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Loader2, ShieldCheck, Upload } from 'lucide-react';
import type { BaseLoadApplyResult, BaseLoadPreview } from '@/lib/types/baseLoads';
import { applyMetlifeGmmBase, previewMetlifeGmmBase } from '@/modules/base-loads/service';

const number = new Intl.NumberFormat('es-MX');
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

function Metric({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'warning' | 'success' }) {
    const styles = tone === 'warning'
        ? 'border-amber-200 bg-amber-50 text-amber-900'
        : tone === 'success'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
            : 'border-slate-200 bg-white text-slate-900';
    return (
        <div className={`rounded-xl border p-4 ${styles}`}>
            <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
            <p className="mt-2 text-2xl font-bold">{number.format(value)}</p>
        </div>
    );
}

export function BaseLoadsView() {
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<BaseLoadPreview | null>(null);
    const [result, setResult] = useState<BaseLoadApplyResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [applying, setApplying] = useState(false);
    const [error, setError] = useState('');

    function selectFile(event: ChangeEvent<HTMLInputElement>) {
        const selected = event.target.files?.[0] || null;
        if (selected && selected.size > MAX_UPLOAD_BYTES) {
            setFile(null);
            setPreview(null);
            setResult(null);
            setError('El archivo supera el límite de 100 MB');
            event.target.value = '';
            return;
        }
        setFile(selected);
        setPreview(null);
        setResult(null);
        setError('');
    }

    async function createPreview() {
        if (!file || loading) return;
        setLoading(true);
        setError('');
        try {
            setPreview(await previewMetlifeGmmBase(file));
        } catch (caught) {
            setError(caught instanceof Error ? caught.message : 'No se pudo analizar el archivo');
        } finally {
            setLoading(false);
        }
    }

    async function applyLoad() {
        if (!preview || applying) return;
        setApplying(true);
        setError('');
        try {
            const applied = await applyMetlifeGmmBase(preview.token);
            setResult(applied);
            setPreview(null);
        } catch (caught) {
            setError(caught instanceof Error ? caught.message : 'No se pudo actualizar la base');
        } finally {
            setApplying(false);
        }
    }

    const stats = preview?.preview;

    return (
        <div className="mx-auto max-w-6xl space-y-6 p-8">
            <div>
                <h1 className="text-3xl font-bold text-white">Carga de bases</h1>
                <p className="mt-2 text-blue-100">Actualiza fuentes canónicas con conciliación, deduplicación y respaldo.</p>
            </div>

            <section className="rounded-2xl bg-white p-6 shadow-xl">
                <div className="flex items-start gap-4">
                    <div className="rounded-xl bg-blue-100 p-3 text-blue-700"><FileSpreadsheet className="h-7 w-7" /></div>
                    <div className="flex-1">
                        <h2 className="text-xl font-semibold text-slate-900">MetLife GMM</h2>
                        <p className="mt-1 text-sm text-slate-600">Reporte de cartera KC. Se filtra por Clave Definitiva y se conserva toda la información de Y en adelante.</p>
                    </div>
                </div>

                <div className="mt-6 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6">
                    <label className="flex cursor-pointer flex-col items-center gap-2 text-center">
                        <Upload className="h-8 w-8 text-slate-500" />
                        <span className="font-medium text-slate-800">Seleccionar reporte .xlsx</span>
                        <span className="text-xs text-slate-500">Máximo 100 MB. La vista previa no modifica la base.</span>
                        <input type="file" accept=".xlsx" onChange={selectFile} className="sr-only" />
                    </label>
                    {file && <p className="mt-4 truncate text-center text-sm font-medium text-blue-700">{file.name}</p>}
                </div>

                <button
                    type="button"
                    onClick={createPreview}
                    disabled={!file || loading || applying}
                    className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                    {loading ? 'Analizando…' : 'Generar vista previa'}
                </button>
            </section>

            {error && (
                <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /><p>{error}</p>
                </div>
            )}

            {stats && (
                <section className="space-y-5 rounded-2xl bg-slate-50 p-6 shadow-xl">
                    <div>
                        <h2 className="text-xl font-semibold text-slate-900">Vista previa obligatoria</h2>
                        <p className="mt-1 text-sm text-slate-600">Archivo: {preview.filename}. Revisa el impacto antes de aplicar.</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <Metric label="Filas del reporte" value={stats.source_rows} />
                        <Metric label="Claves definitivas" value={stats.allowed_agent_keys} />
                        <Metric label="Filas después del filtro" value={stats.rows_after_agent_filter} />
                        <Metric label="Pólizas únicas" value={stats.unique_incoming_policies} />
                        <Metric label="Vigencias únicas" value={stats.unique_policy_periods} />
                        <Metric label="Pólizas actualizadas" value={stats.existing_policies_updated} tone="success" />
                        <Metric label="Pólizas nuevas" value={stats.new_policies_added} tone="success" />
                        <Metric label="Duplicados A–X omitidos" value={stats.duplicate_a_x_rows} />
                        <Metric label="Filas históricas conservadas" value={stats.current_rows_preserved_as_exceptions} tone="warning" />
                    </div>
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
                        Se preservarán datos de Y en adelante en <strong>{number.format(stats.rows_with_preserved_y_plus_data)}</strong> filas. El resultado tendrá <strong>{number.format(stats.final_policy_count)}</strong> pólizas y <strong>{number.format(stats.final_row_count)}</strong> vigencias/variantes A–X. Se creará un respaldo antes de reemplazar la base.
                    </div>
                    <button
                        type="button"
                        onClick={applyLoad}
                        disabled={applying}
                        className="inline-flex items-center rounded-lg bg-emerald-600 px-5 py-2.5 font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {applying ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                        {applying ? 'Actualizando…' : 'Aplicar actualización y crear respaldo'}
                    </button>
                </section>
            )}

            {result && (
                <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 shadow-xl">
                    <div className="flex items-start gap-3 text-emerald-900">
                        <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0" />
                        <div>
                            <h2 className="text-xl font-semibold">Base actualizada</h2>
                            <p className="mt-1 text-sm">Se consolidaron {number.format(result.final_policy_count)} pólizas en {number.format(result.final_row_count)} filas de vigencia. El respaldo quedó en Archivo histórico.</p>
                        </div>
                    </div>
                </section>
            )}
        </div>
    );
}
