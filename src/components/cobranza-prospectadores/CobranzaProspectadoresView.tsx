'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Calculator, CheckCircle2, FileSpreadsheet, Loader2, Plus, Upload, UsersRound, X } from 'lucide-react';
import {
  applyCommissionImport,
  createCommissionPeriod,
  getCommissionPeriodDetail,
  previewCommissionImport,
  type CommissionPeriodDetail,
  type CommissionWorkspace,
  type ImportPreview,
} from '@/modules/cobranza-prospectadores/service';

const sources = [
  { key: 'metlife', label: 'MetLife', help: 'Consolida por póliza y fecha; separa Vida y GMM.' },
  { key: 'sura', label: 'SURA', help: 'Consolida por póliza, recibo, serie y fecha.' },
  { key: 'aarco', label: 'AARCO', help: 'Lee la comisión aplicada ya consolidada.' },
];
const money = (value: number | string) => Number(value || 0).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' });
const monthLabel = (value: string) => new Intl.DateTimeFormat('es-MX', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value.slice(0, 7)}-01T00:00:00Z`));

export function CobranzaProspectadoresView({ initialWorkspace }: { initialWorkspace: CommissionWorkspace }) {
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [selectedPeriod, setSelectedPeriod] = useState(initialWorkspace.periods[0]?.id || '');
  const [detail, setDetail] = useState<CommissionPeriodDetail | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [month, setMonth] = useState('2026-08');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function loadDetail(periodId: string) {
    if (!periodId) { setDetail(null); return; }
    try { setDetail(await getCommissionPeriodDetail(periodId)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo consultar el periodo'); }
  }
  useEffect(() => {
    if (!selectedPeriod) return;
    let cancelled = false;
    getCommissionPeriodDetail(selectedPeriod)
      .then((result) => { if (!cancelled) setDetail(result); })
      .catch((caught) => { if (!cancelled) setError(caught instanceof Error ? caught.message : 'No se pudo consultar el periodo'); });
    return () => { cancelled = true; };
  }, [selectedPeriod]);

  async function addPeriod() {
    setBusy('period'); setError(''); setSuccess('');
    try {
      const result = await createCommissionPeriod(`${month}-01`);
      setWorkspace((current) => ({ ...current, periods: [result.period, ...current.periods], summary: { ...current.summary, periods: current.summary.periods + 1 } }));
      setSelectedPeriod(result.period.id);
      setSuccess(`Periodo ${monthLabel(result.period.month)} creado.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo crear el periodo'); }
    finally { setBusy(''); }
  }

  async function selectFile(source: string, file?: File) {
    if (!file || !selectedPeriod) return;
    setBusy(source); setError(''); setSuccess(''); setPreview(null);
    try { setPreview(await previewCommissionImport(selectedPeriod, source, file)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo generar la vista previa'); }
    finally { setBusy(''); }
  }

  async function applyPreview() {
    if (!preview) return;
    setBusy('apply'); setError('');
    try {
      const result = await applyCommissionImport(preview.token);
      setSuccess(`Carga aplicada: ${result.consolidated_rows} movimientos y ${result.exception_count} excepciones.`);
      setPreview(null);
      await loadDetail(selectedPeriod);
      setWorkspace((current) => ({
        ...current,
        periods: current.periods.map((period) => period.id === selectedPeriod ? { ...period, batch_count: period.batch_count + 1, exception_count: period.exception_count + result.exception_count } : period),
        summary: { ...current.summary, pending_exceptions: current.summary.pending_exceptions + result.exception_count },
      }));
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo aplicar la carga'); }
    finally { setBusy(''); }
  }

  const loadedSources = new Set(detail?.batches.map((batch) => batch.source) || []);
  return <div className="h-full overflow-y-auto p-4 md:p-8"><div className="mx-auto max-w-7xl space-y-5">
    <div><h1 className="text-3xl font-bold text-white">Cobranza para prospectadores</h1><p className="mt-1 text-blue-100">Consolida comisiones recibidas por TAIICO y controla su distribución.</p></div>
    <div className="grid gap-4 sm:grid-cols-4">{[[FileSpreadsheet,'Periodos',workspace.summary.periods],[UsersRound,'Prospectadores activos',workspace.summary.prospectors],[AlertTriangle,'Sin asignar',workspace.summary.pending_exceptions],[Calculator,'Coeficiente fijo',`${Math.round(workspace.summary.fixed_coefficient*100)}%`]].map(([Icon,label,value]) => { const C = Icon as typeof FileSpreadsheet; return <div key={String(label)} className="flex items-center gap-4 rounded-xl bg-white p-5 shadow"><div className="rounded-full bg-violet-100 p-3 text-violet-700"><C /></div><div><p className="text-sm text-slate-500">{String(label)}</p><p className="text-2xl font-bold text-slate-900">{String(value)}</p></div></div>})}</div>
    {(error || success) && <div className={`rounded-xl border p-4 text-sm font-medium ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error || success}</div>}

    <div className="rounded-xl bg-white p-5 shadow"><div className="flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-xl font-bold text-slate-900">Periodos de pago</h2><p className="text-sm text-slate-500">Selecciona un periodo para cargar y conciliar sus tres fuentes.</p></div><div className="flex items-end gap-2"><label className="text-sm font-semibold text-slate-700">Nuevo periodo<input type="month" value={month} onChange={(event)=>setMonth(event.target.value)} className="mt-1 block rounded-lg border p-2.5 font-normal"/></label><button disabled={Boolean(busy) || !month} onClick={addPeriod} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy === 'period' ? <Loader2 className="h-4 w-4 animate-spin"/> : <Plus className="h-4 w-4"/>}Crear</button></div></div>
      <div className="mt-5 overflow-x-auto"><table className="w-full text-left"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-4">Periodo</th><th className="p-4">Estatus</th><th className="p-4">Saldo inicial</th><th className="p-4">Fuentes</th><th className="p-4">Excepciones</th></tr></thead><tbody className="divide-y">{workspace.periods.map((row)=><tr key={row.id} onClick={()=>setSelectedPeriod(row.id)} className={`cursor-pointer ${selectedPeriod === row.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}><td className="p-4 font-semibold capitalize text-slate-900">{monthLabel(row.month)}</td><td className="p-4"><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">{row.status}</span></td><td className="p-4 text-slate-700">{money(row.opening_balance)}</td><td className="p-4 text-slate-700">{row.batch_count} de 3</td><td className="p-4 font-semibold text-slate-700">{row.exception_count}</td></tr>)}{workspace.periods.length===0&&<tr><td colSpan={5} className="p-10 text-center text-slate-500">Crea agosto para iniciar la conciliación.</td></tr>}</tbody></table></div>
    </div>

    {selectedPeriod && <div className="rounded-xl bg-white p-5 shadow"><div className="mb-4"><h2 className="text-xl font-bold text-slate-900">Cargar estados de cuenta</h2><p className="text-sm text-slate-500">La vista previa no modifica el periodo. Podrás revisar las excepciones antes de aplicar.</p></div><div className="grid gap-4 md:grid-cols-3">{sources.map((source) => <div key={source.key} className="rounded-xl border border-slate-200 p-5"><div className="flex items-center justify-between"><h3 className="text-lg font-bold text-slate-900">{source.label}</h3>{loadedSources.has(source.key) && <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5"/>Cargado</span>}</div><p className="mt-2 min-h-10 text-sm text-slate-500">{source.help}</p><label className={`mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-blue-200 px-4 py-3 font-semibold text-blue-700 hover:bg-blue-50 ${busy ? 'pointer-events-none opacity-50' : ''}`}>{busy === source.key ? <Loader2 className="h-4 w-4 animate-spin"/> : <Upload className="h-4 w-4"/>}Generar vista previa<input type="file" accept=".xlsx,.xls" className="hidden" onChange={(event)=>void selectFile(source.key, event.target.files?.[0])}/></label></div>)}</div></div>}

    {detail && detail.batches.length > 0 && <div className="grid gap-5 lg:grid-cols-2"><div className="rounded-xl bg-white p-5 shadow"><h2 className="text-lg font-bold text-slate-900">Cargas aplicadas</h2><div className="mt-3 divide-y">{detail.batches.map((batch)=><div key={batch.id} className="flex items-center justify-between gap-4 py-3"><div><p className="font-semibold uppercase text-slate-900">{batch.source}</p><p className="max-w-sm truncate text-xs text-slate-500">{batch.filename}</p></div><div className="text-right text-sm"><p>{batch.consolidated_rows} movimientos</p><p className={batch.exceptions ? 'text-amber-700' : 'text-emerald-700'}>{batch.exceptions} excepciones</p></div></div>)}</div></div><div className="rounded-xl bg-white p-5 shadow"><h2 className="text-lg font-bold text-slate-900">Excepciones por resolver</h2><div className="mt-3 max-h-72 space-y-3 overflow-y-auto">{detail.exceptions.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">No hay excepciones en este periodo.</p> : detail.exceptions.map((item)=><div key={item.id} className="rounded-lg border border-amber-200 bg-amber-50 p-3"><div className="flex justify-between gap-3"><p className="font-semibold text-slate-900">{item.policy_number}</p><p className="font-semibold text-slate-700">{money(item.source_commission)}</p></div><p className="mt-1 text-xs text-amber-800">{item.reason}</p></div>)}</div></div></div>}

    {preview && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4"><div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-2xl bg-white shadow-2xl"><div className="sticky top-0 flex items-start justify-between border-b bg-white p-5"><div><p className="text-xs font-bold uppercase tracking-wide text-blue-600">Vista previa {preview.source}</p><h2 className="text-xl font-bold text-slate-900">{preview.filename}</h2></div><button onClick={()=>setPreview(null)} className="rounded-full p-2 text-slate-500 hover:bg-slate-100"><X/></button></div><div className="space-y-5 p-5"><div className="grid gap-3 sm:grid-cols-5">{[['Filas origen',preview.summary.raw_rows],['Consolidadas',preview.summary.consolidated_rows],['Listas',preview.summary.ready_rows],['Excepciones',preview.summary.exception_rows],['Total prospectadores',money(preview.summary.prospector_total)]].map(([label,value])=><div key={String(label)} className="rounded-lg bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">{label}</p><p className="mt-1 text-xl font-bold text-slate-900">{value}</p></div>)}</div><div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Póliza</th><th className="p-3">Ramo</th><th className="p-3">Comisión fuente</th><th className="p-3">Prospectador</th><th className="p-3">Resultado</th></tr></thead><tbody className="divide-y">{preview.sample.map((line,index)=><tr key={`${line.policy_number}-${line.receipt_number}-${index}`}><td className="p-3 font-semibold">{line.policy_number}</td><td className="p-3">{line.branch}</td><td className="p-3">{money(line.source_commission)}</td><td className="p-3">{line.allocations.map((item)=>item.prospector_name).join(', ') || '—'}</td><td className="p-3">{line.status === 'listo' ? <span className="text-emerald-700">Listo</span> : <span className="text-amber-700">{line.exception_reason}</span>}</td></tr>)}</tbody></table></div><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-500">Al aplicar, las filas con excepción quedarán detenidas y no generarán comisión.</p><div className="flex gap-2"><button onClick={()=>setPreview(null)} className="rounded-lg border px-4 py-2.5 font-semibold text-slate-700">Cancelar</button><button disabled={busy === 'apply'} onClick={applyPreview} className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 font-semibold text-white disabled:opacity-50">{busy === 'apply' && <Loader2 className="h-4 w-4 animate-spin"/>}Aplicar carga</button></div></div></div></div></div>}
  </div></div>;
}
