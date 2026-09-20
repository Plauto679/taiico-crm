'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle2, Download, Loader2, Plus, Search, X } from 'lucide-react';
import clsx from 'clsx';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { CarteraRecord, CarteraRecordInput } from '@/lib/types/cartera';
import { createCarteraRecord, updateCarteraRecord, getCarteraProspectors, type CarteraProspectorOption } from '@/modules/cartera/service';
import { exportToExcel } from '@/lib/utils/export';

interface Props { data: CarteraRecord[]; insurer: string; type: string; }

const emptyRecord = (insurer: string, type: string): CarteraRecordInput => ({
    policy_number: '', current_policy_number: '', contractor: '', prospector: '',
    percentage: 0, payment_start_date: null,
    insurer: insurer === 'AARCO' ? 'aarco' : insurer.toLowerCase(), carrier: '',
    policy_type: type === 'ALL' ? 'VIDA' : type,
});

export function CarteraView({ data, insurer, type }: Props) {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [editing, setEditing] = useState<CarteraRecord | null>(null);
    const [creating, setCreating] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [visibleData, setVisibleData] = useState(data);
    const [generalSearch, setGeneralSearch] = useState('');
    const [exportRows, setExportRows] = useState(data);
    const [isNavigationPending, startNavigation] = useTransition();
    const [pendingDestination, setPendingDestination] = useState('');

    useEffect(() => {
        // A server refresh is authoritative and must replace the optimistic rows.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setVisibleData(data);
    }, [data]);

    useEffect(() => {
        if (!successMessage) return;
        const timer = window.setTimeout(() => setSuccessMessage(''), 5000);
        return () => window.clearTimeout(timer);
    }, [successMessage]);

    const navigate = (nextInsurer: string, nextType?: string) => {
        if (isNavigationPending) return;
        const params = new URLSearchParams(searchParams.toString());
        params.set('insurer', nextInsurer);
        if (nextInsurer === 'Metlife') params.set('type', nextType || 'VIDA');
        else if (nextType) params.set('type', nextType);
        else params.delete('type');
        const nextLabel = nextInsurer === 'Metlife' ? `${nextInsurer} ${nextType || 'VIDA'}` : nextInsurer;
        setPendingDestination(nextLabel);
        startNavigation(() => router.push(`/cartera?${params}`));
    };

    const columns = useMemo<Column<CarteraRecord>[]>(() => {
        const next: Column<CarteraRecord>[] = [];
        if (insurer === 'AARCO') {
            next.push({ header: 'Aseguradora', accessorKey: (row) => row.carrier || 'Sin especificar', filterValue: (row) => row.carrier || 'Sin especificar' });
        }
        next.push({ header: 'Póliza', accessorKey: 'policy_number' });
        if (insurer === 'Metlife' && type === 'GMM') {
            next.push({ header: 'Póliza actual', accessorKey: 'current_policy_number' });
        }
        next.push(
            { header: 'Contratante', accessorKey: 'contractor' },
            { header: 'Prospectador', accessorKey: 'prospector' },
            { header: 'Inicio de pago', accessorKey: 'payment_start_date' },
            { header: 'Porcentaje', accessorKey: (row) => `${Number(row.percentage || 0).toFixed(0)}%`, filterValue: (row) => Number(row.percentage || 0).toFixed(0) },
        );
        return next;
    }, [insurer, type]);

    const searchedData = useMemo(() => {
        const query = generalSearch.trim().toLocaleLowerCase('es');
        if (!query) return visibleData;

        return visibleData.filter((item) => [
            item.policy_number,
            item.current_policy_number,
            item.carrier,
            item.contractor,
            item.prospector,
            item.payment_start_date,
            Number(item.percentage || 0).toFixed(0),
            `${Number(item.percentage || 0).toFixed(0)}%`,
        ].some((value) => String(value ?? '').toLocaleLowerCase('es').includes(query)));
    }, [generalSearch, visibleData]);

    const captureProcessedRows = useCallback((rows: CarteraRecord[]) => setExportRows(rows), []);

    const exportCurrentView = () => {
        const rows = exportRows.map((item) => ({
            ...(insurer === 'AARCO' ? { 'Aseguradora': item.carrier || '' } : {}),
            'Póliza': item.policy_number,
            ...(insurer === 'Metlife' && type === 'GMM' ? { 'Póliza actual': item.current_policy_number || '' } : {}),
            'Contratante': item.contractor,
            'Prospectador': item.prospector,
            'Inicio de pago': item.payment_start_date || '',
            'Porcentaje': Number(item.percentage || 0) / 100,
        }));
        const safeInsurer = insurer.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '');
        const branch = type === 'ALL' ? '' : `-${type}`;
        const date = new Date().toISOString().slice(0, 10);
        exportToExcel(rows, `Cartera-Prospectadores-${safeInsurer}${branch}-${date}.xlsx`);
    };

    const record = editing || (creating ? ({ id: '', ...emptyRecord(insurer, type) } as CarteraRecord) : null);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); setSaving(true); setError('');
        const form = new FormData(event.currentTarget);
        const payload: CarteraRecordInput = {
            policy_number: String(form.get('policy_number') || '').trim(),
            current_policy_number: String(form.get('current_policy_number') || '').trim() || null,
            contractor: String(form.get('contractor') || '').trim(),
            prospector: String(form.get('prospector') || '').trim(),
            percentage: Number(form.get('percentage') || 0),
            payment_start_date: String(form.get('payment_start_date') || '').trim() || null,
            insurer: insurer === 'AARCO' ? 'aarco' : insurer.toLowerCase(),
            carrier: insurer === 'AARCO' ? String(form.get('carrier') || '').trim() : null,
            policy_type: type === 'ALL' ? (record?.policy_type || 'VIDA') : type,
        };
        try {
            const wasEditing = Boolean(editing);
            const savedRecord = editing
                ? await updateCarteraRecord(editing.id, payload)
                : await createCarteraRecord(payload);
            setVisibleData((current) => {
                const recordExists = current.some((item) => item.id === savedRecord.id);
                const next = recordExists
                    ? current.map((item) => item.id === savedRecord.id ? savedRecord : item)
                    : [...current, savedRecord];
                return next.sort((left, right) => left.policy_number.localeCompare(right.policy_number, 'es', { numeric: true }));
            });
            setEditing(null); setCreating(false); router.refresh();
            setSuccessMessage(wasEditing ? 'Registro actualizado correctamente.' : 'Registro guardado correctamente.');
        } catch (cause) {
            setError(cause instanceof Error ? cause.message.replace(/^API Error:\s*/, '') : 'No fue posible guardar el registro');
        } finally { setSaving(false); }
    }

    return <div className="flex h-full min-h-0 flex-col gap-4">
        {successMessage && <div role="status" aria-live="polite" className="fixed right-4 top-4 z-[100] flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-emerald-200 bg-white px-5 py-4 font-semibold text-emerald-800 shadow-2xl sm:right-6 sm:top-6">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-emerald-100"><CheckCircle2 className="h-5 w-5" /></span>
            <span>{successMessage}</span>
            <button type="button" aria-label="Cerrar confirmación" onClick={() => setSuccessMessage('')} className="ml-2 rounded-full p-1 text-emerald-700 hover:bg-emerald-50"><X className="h-4 w-4" /></button>
        </div>}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/30 pb-3">
            <div className="flex flex-wrap gap-2">
                {[
                    { value: 'Metlife', label: 'Metlife' },
                    { value: 'SURA', label: 'SURA' },
                    { value: 'AARCO', label: 'AARCO' },
                ].map((item) => <button key={item.value} disabled={isNavigationPending} onClick={() => navigate(item.value)} className={clsx('rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-wait', insurer === item.value || pendingDestination.startsWith(item.value) ? 'bg-[#5996D1] text-white ring-2 ring-white/70' : 'text-white hover:bg-white/10')}>{item.label}</button>)}
            </div>
            <button type="button" onClick={() => { setCreating(true); setEditing(null); setError(''); }} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white shadow hover:bg-blue-700"><Plus className="h-5 w-5" /> Nuevo registro</button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">{insurer === 'Metlife' && ['VIDA', 'GMM'].map((item) => <button key={item} disabled={isNavigationPending} onClick={() => navigate('Metlife', item)} className={clsx('rounded-full border px-4 py-1.5 text-sm font-semibold disabled:cursor-wait', type === item || pendingDestination === `Metlife ${item}` ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-300 bg-white text-gray-700')}>{item}</button>)}
                {isNavigationPending && <span role="status" className="ml-2 inline-flex items-center gap-2 text-sm font-semibold text-white"><Loader2 className="h-4 w-4 animate-spin" /> Cargando {pendingDestination}…</span>}
            </div>
            <button type="button" onClick={exportCurrentView} disabled={!exportRows.length} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">
                <Download className="h-4 w-4" /> Exportar Excel
            </button>
        </div>
        <div className="relative w-full max-w-2xl">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
            <input
                type="search"
                value={generalSearch}
                onChange={(event) => setGeneralSearch(event.target.value)}
                placeholder="Buscar en cualquier columna…"
                aria-label="Buscar en cualquier columna"
                className="w-full rounded-lg border border-white/40 bg-white py-2.5 pl-11 pr-4 text-sm text-slate-900 shadow-sm outline-none placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-200"
            />
        </div>
        <div className="min-h-0 flex-1 overflow-auto overscroll-contain rounded-lg bg-white shadow">
            <DataTable data={searchedData} columns={columns} filterMode="multi-select" pageSize={150} onProcessedDataChange={captureProcessedRows} onRowClick={setEditing} className="max-h-full min-w-full overflow-auto border-0 shadow-none" />
        </div>
        {record && <div className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-slate-950/45 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) { setEditing(null); setCreating(false); } }}>
            <form key={record.id || 'new'} onSubmit={submit} className="my-auto w-full max-w-2xl rounded-2xl bg-white shadow-2xl">
                <div className="flex items-start justify-between border-b px-6 py-5"><div><h2 className="text-2xl font-bold text-slate-900">{editing ? 'Editar registro' : 'Nuevo registro'}</h2><p className="text-sm text-slate-500">{insurer}{type !== 'ALL' ? ` · ${type}` : ''}</p></div><button type="button" onClick={() => { setEditing(null); setCreating(false); }} className="rounded-full p-2 text-slate-400 hover:bg-slate-100"><X /></button></div>
                <div className="grid gap-4 p-6 sm:grid-cols-2">
                    {insurer === 'AARCO' && <Field label="Aseguradora" name="carrier" defaultValue={record.carrier || ''} placeholder="Ej. AXA, Mapfre, HDI…" required />}
                    <Field label="Póliza" name="policy_number" defaultValue={record.policy_number} required />
                    {insurer === 'Metlife' && type === 'GMM' && <Field label="Póliza actual" name="current_policy_number" defaultValue={record.current_policy_number || ''} />}
                    <Field label="Contratante" name="contractor" defaultValue={record.contractor} required wide />
                    <ProspectorSelect currentValue={record.prospector} />
                    <div className="grid gap-1.5">
                        <Field label="Inicio de pago" name="payment_start_date" type="date" defaultValue={record.payment_start_date || ''} />
                        <p className="text-xs text-slate-500">Sin fecha: aplica a movimientos pasados y futuros, sin vencimiento. Con fecha: aplica durante un año desde ese inicio.</p>
                    </div>
                    <Field label="Porcentaje" name="percentage" type="number" min="0" max="100" step="0.01" defaultValue={String(record.percentage ?? 0)} required />
                    {error && <p className="sm:col-span-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
                </div>
                <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4"><button type="button" onClick={() => { setEditing(null); setCreating(false); }} className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-700">Cancelar</button><button disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-60">{saving ? 'Guardando…' : 'Guardar'}</button></div>
            </form>
        </div>}
    </div>;
}

function Field({ label, wide, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string; wide?: boolean }) {
    return <label className={clsx('grid gap-1.5 text-sm font-semibold text-slate-700', wide && 'sm:col-span-2')}>{label}<input {...props} className="rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></label>;
}

function ProspectorSelect({ currentValue }: { currentValue: string }) {
    const [selectedValue, setSelectedValue] = useState(currentValue || '');
    const [options, setOptions] = useState<CarteraProspectorOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');
    const [attempt, setAttempt] = useState(0);
    useEffect(() => {
        let cancelled = false;
        getCarteraProspectors().then(({ prospectors }) => {
            if (!cancelled) {
                setOptions(prospectors.sort((a, b) => a.name.localeCompare(b.name, 'es')));
                setLoading(false);
            }
        }).catch(() => {
            if (!cancelled) {
                setLoadError('No se pudo cargar el catálogo de prospectadores.');
                setLoading(false);
            }
        });
        return () => { cancelled = true; };
    }, [attempt]);
    const names = [...new Set(options.map(option => option.name))];
    return <label className="grid gap-1.5 text-sm font-semibold text-slate-700">
        Prospectador
        <select name="prospector" value={selectedValue} onChange={event => setSelectedValue(event.target.value)} required
            aria-busy={loading}
            className="min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100">
            <option value="" disabled>{loading ? 'Cargando prospectadores…' : 'Selecciona un prospectador'}</option>
            {currentValue && !names.includes(currentValue) && <option value={currentValue}>{currentValue} (asignación actual)</option>}
            {names.map(name => <option key={name} value={name}>{name}</option>)}
        </select>
        {!loading && !loadError && names.length === 0 && <span className="font-normal text-slate-600">No hay prospectadores activos. Regístralos en el módulo Prospectadores.</span>}
        {loadError && <span role="alert" className="font-normal text-red-700">{loadError}{' '}
            <button type="button" className="underline" onClick={() => { setLoadError(''); setLoading(true); setAttempt(value => value + 1); }}>Reintentar</button>
        </span>}
    </label>;
}
