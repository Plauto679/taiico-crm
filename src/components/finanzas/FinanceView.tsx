'use client';

import { useMemo, useState } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Check, ChevronDown, ChevronUp, Download, FileSearch, Landmark, Loader2, Plus, RefreshCw, Search, SlidersHorizontal, Trash2, Upload, X } from 'lucide-react';
import { DataTable } from '@/components/ui/DataTable';
import {
  Budget, Company, FinanceCategories, FinanceFilters, FinanceInvoice, FinanceMovement, FinanceOverview, Projection, RecurringGroup, Rule,
  applyRule, cancelProjection, createProjection, createRule, decideRecurring, deleteRule,
  exportMovements, exportRecurringMovements, getBudgets, getCashFlow, getFinanceOverview, getInvoiceSuggestions, getInvoices, getMovements, getRecurring, getRules,
  matchInvoice, previewIngestion, previewRule, publishIngestion, revertRule, scanInvoices, syncSources, updateMovement, upsertBudget,
} from '@/modules/finanzas/service';

const TABS = ['Resumen', 'Movimientos', 'Recurrentes', 'Facturas', 'Flujo y presupuesto', 'Clasificación'] as const;
type Tab = typeof TABS[number];
type FinanceScope = { company: Company; filters: FinanceFilters };
type MovementQuery = FinanceScope & { search: string };
const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium' });

function ErrorMessage({ text }: { text: string }) {
  return text ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{text}</div> : null;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-52 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">{children}</div>;
}

function Kpi({ label, value, tone = 'slate' }: { label: string; value: string; tone?: 'slate' | 'green' | 'amber' | 'red' }) {
  const colors = { slate: 'border-slate-200', green: 'border-emerald-300', amber: 'border-amber-300', red: 'border-red-300' };
  return <div className={`rounded-xl border-l-4 bg-white p-4 shadow-sm ${colors[tone]}`}><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-2xl font-bold text-slate-900">{value}</p></div>;
}

export function FinanceView({ initialOverview, categories }: { initialOverview: FinanceOverview; categories: FinanceCategories }) {
  const [tab, setTab] = useState<Tab>('Resumen');
  const [company, setCompany] = useState<Company>('CONSOLIDADO');
  const [bank, setBank] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [overview, setOverview] = useState(initialOverview);
  const [movements, setMovements] = useState<FinanceMovement[]>([]);
  const [movementTotal, setMovementTotal] = useState(0);
  const [movementQuery, setMovementQuery] = useState<MovementQuery>({ company: 'CONSOLIDADO', search: '', filters: {} });
  const [search, setSearch] = useState('');
  const [recurring, setRecurring] = useState<RecurringGroup[]>([]);
  const [recurringScope, setRecurringScope] = useState<FinanceScope>({ company: 'CONSOLIDADO', filters: {} });
  const [invoices, setInvoices] = useState<FinanceInvoice[]>([]);
  const [invoiceFolder, setInvoiceFolder] = useState(false);
  const [projections, setProjections] = useState<Projection[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(true);

  async function load(activeTab = tab, activeCompany = company, filters: FinanceFilters = { bank, startDate, endDate }) {
    setLoading(true); setError('');
    try {
      if (activeTab === 'Resumen') setOverview(await getFinanceOverview(activeCompany, filters));
      if (activeTab === 'Movimientos') { const activeSearch = search; const response = await getMovements(activeCompany, activeSearch, filters); setMovements(response.items); setMovementTotal(response.total); setMovementQuery({ company: activeCompany, search: activeSearch, filters }); }
      if (activeTab === 'Recurrentes') { setRecurring((await getRecurring(activeCompany, filters)).items); setRecurringScope({ company: activeCompany, filters }); }
      if (activeTab === 'Facturas') { const response = await getInvoices(); setInvoices(response.items); setInvoiceFolder(response.folder_available); }
      if (activeTab === 'Flujo y presupuesto') { const [flow, budget] = await Promise.all([getCashFlow(activeCompany), getBudgets(activeCompany)]); setProjections(flow.items); setBudgets(budget.items); }
      if (activeTab === 'Clasificación') setRules((await getRules()).items);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo cargar Finanzas'); }
    finally { setLoading(false); }
  }

  function chooseTab(value: Tab) { setTab(value); void load(value, company); }
  function chooseCompany(value: Company) { setCompany(value); void load(tab, value, { bank, startDate, endDate }); }
  function applyScope() { void load(tab, company, { bank, startDate, endDate }); }
  function resetScope() { setBank(''); setStartDate(''); setEndDate(''); void load(tab, company, {}); }

  return <div className="mx-auto flex h-full min-h-0 w-full max-w-[1600px] flex-col gap-4 overflow-hidden px-3 py-4 text-slate-900 sm:px-5 md:py-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="flex items-center gap-2 text-2xl font-bold text-white"><Landmark className="h-6 w-6" />Finanzas</h1><p className="text-sm text-blue-100">Salud financiera, conciliación y planeación con trazabilidad a la fuente.</p></div>
      <div className="flex gap-2">
        <button onClick={() => setUploadOpen(true)} className="flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-600"><Upload className="h-4 w-4" />Cargar estados</button>
        <button onClick={() => load()} disabled={loading} className="rounded-lg border border-white/30 bg-white/10 p-2.5 text-white hover:bg-white/20" title="Actualizar"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>
      </div>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white p-2 shadow">
      <div className="flex max-w-full gap-1 overflow-x-auto">{TABS.map((item) => <button key={item} onClick={() => chooseTab(item)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold ${tab === item ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{item}</button>)}</div>
      <div className="flex rounded-lg bg-slate-100 p-1">{(['CONSOLIDADO', 'TLA', 'TS'] as Company[]).map((item) => <button key={item} onClick={() => chooseCompany(item)} className={`rounded-md px-3 py-1.5 text-xs font-bold ${company === item ? 'bg-white text-emerald-700 shadow' : 'text-slate-500'}`}>{item === 'CONSOLIDADO' ? 'Consolidado' : item}</button>)}</div>
    </div>
    {(tab === 'Resumen' || tab === 'Movimientos' || tab === 'Recurrentes') && <section className="rounded-xl bg-white p-3 shadow">
      <button
        type="button"
        onClick={() => setScopeOpen((current) => !current)}
        aria-expanded={scopeOpen}
        aria-controls="finance-scope-controls"
        className="flex w-full items-center justify-between gap-3 rounded-lg px-1 py-1 text-left text-sm font-bold text-slate-700 hover:text-emerald-700"
      >
        <span className="flex min-w-0 items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 shrink-0" />
          <span className="shrink-0">Filtros de periodo y banco</span>
          {!scopeOpen && <span className="truncate text-xs font-medium text-slate-500">{startDate || endDate ? `${startDate || 'Inicio abierto'} → ${endDate || 'Fin abierto'}` : 'Todas las fechas'} · {bank || 'Todos los bancos'}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-slate-500">
          {scopeOpen ? 'Ocultar' : 'Mostrar'}
          {scopeOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </span>
      </button>
      {scopeOpen && <div id="finance-scope-controls" className="mt-3 grid gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2 lg:grid-cols-[minmax(150px,1fr),minmax(150px,1fr),minmax(160px,1fr),auto] lg:items-end">
        <label className="text-xs font-semibold text-slate-600">Fecha inicial<input type="date" value={startDate} max={endDate || undefined} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900" /></label>
        <label className="text-xs font-semibold text-slate-600">Fecha final<input type="date" value={endDate} min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900" /></label>
        <label className="text-xs font-semibold text-slate-600">Banco<select value={bank} onChange={(event) => setBank(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"><option value="">Todos los bancos</option><option value="AMEX">AMEX</option><option value="BBVA">BBVA</option><option value="BANORTE">Banorte</option></select></label>
        <div className="flex gap-2 sm:col-span-2 lg:col-span-1"><button onClick={applyScope} disabled={!!startDate && !!endDate && startDate > endDate} className="flex-1 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-40">Aplicar</button><button onClick={resetScope} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600">Restablecer</button></div>
      </div>}
    </section>}
    <ErrorMessage text={error} />
    <div className="min-h-0 flex-1 overflow-auto rounded-2xl bg-white/95 p-4 shadow-xl md:p-6">
      {loading && <div className="mb-3 flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />Actualizando información…</div>}
      {tab === 'Resumen' && <Summary overview={overview} scopedPeriod={!!startDate || !!endDate} onSync={async () => { setLoading(true); try { await syncSources(); await load('Resumen', company); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo sincronizar'); } finally { setLoading(false); } }} />}
      {tab === 'Movimientos' && <Movements key={`${movementQuery.company}|${movementQuery.search}|${JSON.stringify(movementQuery.filters)}|${movements.length === 0}`} items={movements} total={movementTotal} query={movementQuery} loading={loading} categories={categories} search={search} setSearch={setSearch} onSearch={() => load('Movimientos')} onSaved={(saved) => setMovements((current) => current.map((item) => item.id === saved.id ? saved : item))} />}
      {tab === 'Recurrentes' && <Recurring items={recurring} scope={recurringScope} onDecide={async (fingerprint, status) => { await decideRecurring(fingerprint, status); await load('Recurrentes', recurringScope.company, recurringScope.filters); }} />}
      {tab === 'Facturas' && <Invoices items={invoices} folderAvailable={invoiceFolder} onScan={async () => { const result = await scanInvoices(); if (result.message) setError(result.message); await load('Facturas'); }} onRefresh={() => load('Facturas')} />}
      {tab === 'Flujo y presupuesto' && <CashFlow items={projections} budgets={budgets} company={company} categories={categories} onRefresh={() => load('Flujo y presupuesto')} />}
      {tab === 'Clasificación' && <Rules items={rules} categories={categories} onRefresh={() => load('Clasificación')} setError={setError} />}
    </div>
    {uploadOpen && <UploadWizard onClose={() => setUploadOpen(false)} onPublished={async () => { setUploadOpen(false); await load('Resumen'); }} />}
  </div>;
}

function Summary({ overview, scopedPeriod, onSync }: { overview: FinanceOverview; scopedPeriod: boolean; onSync: () => Promise<void> }) {
  const k = overview.kpis;
  const periodLabel = scopedPeriod ? 'del periodo' : 'del mes';
  return <div className="space-y-6">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Kpi label="Efectivo activo" value={money.format(k.active_cash)} tone="green" /><Kpi label="Pasivo tarjetas" value={money.format(k.credit_liability)} tone="red" /><Kpi label={`Flujo neto ${periodLabel}`} value={money.format(k.net_flow_month)} tone={k.net_flow_month >= 0 ? 'green' : 'red'} /><Kpi label="Sin clasificar" value={String(k.unclassified)} tone={k.unclassified ? 'amber' : 'green'} /><Kpi label="Facturas pendientes" value={String(k.invoice_gaps)} tone={k.invoice_gaps ? 'amber' : 'green'} />
    </div>
    <div className="grid gap-4 xl:grid-cols-[2fr,1fr]">
      <section className="rounded-xl border border-slate-200 p-4"><h2 className="font-bold">Entradas y salidas</h2>{overview.monthly.length ? <div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><AreaChart data={overview.monthly}><defs><linearGradient id="income" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#059669" stopOpacity={.35}/><stop offset="95%" stopColor="#059669" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(value) => money.format(Number(value))} /><Area type="monotone" dataKey="entries" name="Entradas" stroke="#059669" fill="url(#income)" /><Area type="monotone" dataKey="exits" name="Salidas" stroke="#dc2626" fill="#fecaca" /></AreaChart></ResponsiveContainer></div> : <Empty>Sin movimientos indexados para graficar.</Empty>}</section>
      <section className="rounded-xl border border-slate-200 p-4"><div className="flex items-center justify-between"><h2 className="font-bold">Fuentes</h2><button onClick={onSync} className="text-xs font-bold text-emerald-700 hover:underline">Sincronizar</button></div><div className="mt-3 space-y-2">{overview.sources.length ? overview.sources.map((source) => <div key={source.key} className="rounded-lg bg-slate-50 p-3"><div className="flex items-center justify-between"><span className="font-semibold">{source.company} · {source.bank}</span><span className={`h-2.5 w-2.5 rounded-full ${source.available ? 'bg-emerald-500' : 'bg-amber-500'}`} /></div><p className="mt-1 text-xs text-slate-500">{source.available ? `${source.row_count} movimientos · ${source.last_synced_at ? dateFormat.format(new Date(source.last_synced_at)) : 'pendiente de sincronizar'}` : source.error || 'Fuente no disponible'}</p></div>) : <p className="text-sm text-slate-500">Pulsa Sincronizar para registrar el estado de las fuentes.</p>}</div></section>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Kpi label={`Entradas ${periodLabel}`} value={money.format(k.entries_month)} /><Kpi label={`Salidas ${periodLabel}`} value={money.format(k.exits_month)} /><Kpi label={`Impuestos ${periodLabel}`} value={money.format(k.tax_month)} /><Kpi label="Compromisos futuros" value={money.format(k.future_commitments)} /></div>
  </div>;
}

function Movements({ items, total, query, loading, categories, search, setSearch, onSearch, onSaved }: { items: FinanceMovement[]; total: number; query: MovementQuery; loading: boolean; categories: FinanceCategories; search: string; setSearch: (value: string) => void; onSearch: () => void; onSaved: (item: FinanceMovement) => void }) {
  const [editing, setEditing] = useState<FinanceMovement | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [columnFilters, setColumnFilters] = useState<Record<string, string[]>>({});
  const columns = useMemo(() => [
    { header: 'Fecha', accessorKey: 'fecha_operacion' as const, cell: (item: FinanceMovement) => dateFormat.format(new Date(`${item.fecha_operacion}T12:00:00`)) },
    { header: 'Empresa', accessorKey: 'empresa' as const },
    { header: 'Banco', accessorKey: 'banco' as const },
    { header: 'Descripción original', accessorKey: 'descripcion_original' as const, cell: (item: FinanceMovement) => <div className="max-w-sm"><p className="truncate font-medium">{item.descripcion_original}</p><p className="truncate text-xs text-slate-500">{item.contraparte || item.referencia || '—'}</p></div> },
    { header: 'Descripción interna', accessorKey: 'descripcion' as const, cell: (item: FinanceMovement) => <span className="block max-w-xs truncate" title={item.descripcion}>{item.descripcion || '—'}</span> },
    { header: 'Categoría', accessorKey: 'categoria' as const, cell: (item: FinanceMovement) => item.categoria || <span className="text-amber-700">Sin clasificar</span> },
    { header: 'Importe', accessorKey: 'importe_neto' as const, cell: (item: FinanceMovement) => <span className={`font-semibold ${item.importe_neto < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{money.format(item.importe_neto)}</span> },
    { header: 'Recurrente', accessorKey: (item: FinanceMovement) => item.recurrente ? 'Sí' : 'No', filterValue: (item: FinanceMovement) => item.recurrente ? 'Sí' : 'No', cell: (item: FinanceMovement) => <span className={item.recurrente ? 'font-semibold text-emerald-700' : 'text-slate-600'} title={item.recurrente ? 'Confirmado como recurrente' : 'No confirmado como recurrente'}>{item.recurrente ? 'Sí' : 'No'}</span> },
    { header: 'Factura', accessorKey: (item: FinanceMovement) => item.factura_uuid ? 'Conciliada' : item.requiere_factura ? 'Pendiente' : '', filterValue: (item: FinanceMovement) => item.factura_uuid ? 'Conciliada' : item.requiere_factura ? 'Pendiente' : '', cell: (item: FinanceMovement) => item.factura_uuid ? <Check className="h-4 w-4 text-emerald-600" /> : item.requiere_factura ? <AlertTriangle className="h-4 w-4 text-amber-500" /> : '—' },
    { header: 'Fuente', accessorKey: 'archivo_fuente' as const, cell: (item: FinanceMovement) => <span className="text-xs text-slate-500">{item.archivo_fuente || '—'}{item.pagina_fuente ? ` · p.${item.pagina_fuente}` : ''}</span> },
  ], []);
  return <div className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex w-full max-w-xl"><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && onSearch()} placeholder="Buscar descripción original o interna, contraparte, referencia o ID" className="min-w-0 flex-1 rounded-l-lg border border-slate-300 px-3 py-2 text-sm" /><button onClick={onSearch} className="rounded-r-lg bg-slate-900 px-3 text-white"><Search className="h-4 w-4" /></button></div><div className="flex items-center gap-3"><span className="text-sm text-slate-500">{total.toLocaleString('es-MX')} movimientos</span><button disabled={exporting || loading} onClick={async () => { setExporting(true); setExportError(''); try { await exportMovements(query.company, query.search, query.filters, columnFilters); } catch (reason) { setExportError(reason instanceof Error ? reason.message : 'No se pudo exportar el Excel'); } finally { setExporting(false); } }} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-50">{exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Exportar a Excel</button></div></div>
    {exportError && <ErrorMessage text={exportError} />}
    {items.length ? <DataTable data={items} columns={columns} filterMode="multi-select" onMultiFiltersChange={setColumnFilters} onRowClick={setEditing} className="max-h-[calc(100dvh-25rem)] overflow-auto rounded-xl" /> : <Empty>No hay movimientos. Sincroniza las fuentes o revisa los filtros.</Empty>}
    {editing && <MovementEditor item={editing} categories={categories} onClose={() => setEditing(null)} onSave={async (payload) => { const response = await updateMovement(editing.id, payload); onSaved(response.movement); setEditing(null); }} />}
  </div>;
}

function ClassificationFields({ categories, category, subcategory, onCategoryChange, onSubcategoryChange }: { categories: FinanceCategories; category: string; subcategory: string; onCategoryChange: (value: string) => void; onSubcategoryChange: (value: string) => void }) {
  return <div className="grid gap-4 sm:grid-cols-2">
    <label className="text-sm font-semibold">Categoría
      <select value={category} onChange={(event) => { onCategoryChange(event.target.value); onSubcategoryChange(''); }} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal text-slate-900">
        <option value="">Sin clasificación manual</option>
        {Object.keys(categories).map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
    <label className="text-sm font-semibold">Subcategoría
      <select value={subcategory} onChange={(event) => onSubcategoryChange(event.target.value)} disabled={!category} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal text-slate-900 disabled:bg-slate-100">
        <option value="">Selecciona una subcategoría</option>
        {(categories[category] || []).map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
  </div>;
}

function MovementEditor({ item, categories, onClose, onSave }: { item: FinanceMovement; categories: FinanceCategories; onClose: () => void; onSave: (payload: Record<string, unknown>) => Promise<void> }) {
  const initialCategory = Object.hasOwn(categories, item.categoria) ? item.categoria : '';
  const initialSubcategory = (categories[initialCategory] || []).includes(item.subcategoria) ? item.subcategoria : '';
  const [category, setCategory] = useState(initialCategory);
  const [subcategory, setSubcategory] = useState(initialSubcategory);
  const [description, setDescription] = useState(item.descripcion || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const classificationChanged = category !== initialCategory || subcategory !== initialSubcategory;

  async function save() {
    setSaving(true); setError('');
    const payload: Record<string, unknown> = { descripcion: description.trim() || null };
    if (classificationChanged) {
      payload.categoria = category || null;
      payload.subcategoria = subcategory || null;
    }
    try { await onSave(payload); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar el movimiento'); }
    finally { setSaving(false); }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"><div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
    <div className="flex justify-between"><div><h2 className="text-lg font-bold">Clasificar movimiento</h2><p className="mt-1 text-sm text-slate-500">Descripción original: {item.descripcion_original}</p></div><button onClick={onClose} aria-label="Cerrar"><X /></button></div>
    <div className="mt-5"><ClassificationFields categories={categories} category={category} subcategory={subcategory} onCategoryChange={setCategory} onSubcategoryChange={setSubcategory} /></div>
    {item.categoria && !Object.hasOwn(categories, item.categoria) && <p className="mt-3 text-xs text-amber-700">Clasificación anterior: {item.categoria}{item.subcategoria ? ` / ${item.subcategoria}` : ''}. Puedes conservarla o sustituirla por una del catálogo.</p>}
    <label className="mt-4 block text-sm font-semibold">Descripción interna
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} rows={3} placeholder="Explica a qué corresponde este movimiento; no modifica el texto del banco" className="mt-1 block w-full resize-y rounded-lg border border-slate-300 px-3 py-2 font-normal text-slate-900" />
    </label>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <div className="mt-6 flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border px-4 py-2">Cancelar</button><button disabled={saving || (classificationChanged && !!category && !subcategory)} onClick={save} className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white disabled:opacity-50">{saving ? 'Guardando…' : 'Guardar'}</button></div>
  </div></div>;
}

function Recurring({ items, scope, onDecide }: { items: RecurringGroup[]; scope: FinanceScope; onDecide: (fingerprint: string, status: string) => Promise<void> }) {
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<{ fingerprint: string; message: string } | null>(null);
  const [statusFilter, setStatusFilter] = useState<'todos' | 'pendiente' | 'confirmado' | 'descartado'>('todos');
  const visibleItems = statusFilter === 'todos' ? items : items.filter((item) => item.status === statusFilter);

  async function exportGroup(fingerprint: string) {
    setExporting(fingerprint);
    setExportError(null);
    try {
      await exportRecurringMovements(fingerprint, scope.company, scope.filters);
    } catch (reason) {
      setExportError({ fingerprint, message: reason instanceof Error ? reason.message : 'No se pudo exportar el Excel' });
    } finally {
      setExporting(null);
    }
  }

  return <div className="space-y-3">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-bold">Detección explicable de recurrentes</h2><p className="text-sm text-slate-500">La decisión humana se conserva y prevalece sobre futuras sugerencias.</p></div><label className="text-sm font-semibold text-slate-700">Estatus<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} className="mt-1 block min-w-44 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-900"><option value="todos">Todos</option><option value="pendiente">Pendiente</option><option value="confirmado">Confirmado</option><option value="descartado">Descartado</option></select></label></div>
    <p className="text-xs text-slate-500">Mostrando {visibleItems.length} de {items.length} patrones</p>
    {visibleItems.length ? visibleItems.map((item) => <div key={item.fingerprint} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4">
      <div><p className="font-semibold">{item.label}</p><p className="text-xs text-slate-500">{item.company} · {item.occurrences} movimientos en {item.months} meses · promedio {money.format(item.average_amount)}</p><p className="mt-1 text-xs text-slate-400">{item.basis}</p>{exportError?.fingerprint === item.fingerprint && <p role="alert" className="mt-2 text-xs font-medium text-red-700">{exportError.message}</p>}</div>
      <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${item.status === 'confirmado' ? 'bg-emerald-100 text-emerald-700' : item.status === 'descartado' ? 'bg-slate-100 text-slate-600' : 'bg-amber-100 text-amber-700'}`}>{item.status}</span><button onClick={() => onDecide(item.fingerprint, 'confirmado')} className="rounded-lg border border-emerald-300 px-3 py-1.5 text-xs font-bold text-emerald-700">Confirmar</button><button onClick={() => onDecide(item.fingerprint, 'descartado')} className="rounded-lg border px-3 py-1.5 text-xs font-bold">Descartar</button><button type="button" disabled={exporting === item.fingerprint} onClick={() => exportGroup(item.fingerprint)} className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-50 disabled:opacity-50">{exporting === item.fingerprint ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}Exportar Excel</button></div>
    </div>) : <Empty>{items.length ? 'No hay patrones recurrentes con el estatus seleccionado.' : 'No hay patrones recurrentes suficientes con la información indexada.'}</Empty>}
  </div>;
}

function Invoices({ items, folderAvailable, onScan, onRefresh }: { items: FinanceInvoice[]; folderAvailable: boolean; onScan: () => Promise<void>; onRefresh: () => Promise<void> }) {
  const [suggestions, setSuggestions] = useState<{ invoice: FinanceInvoice; items: Array<{ movement: FinanceMovement; confidence: number; rationale: string }> } | null>(null);
  const columns = useMemo(() => [
    { header: 'Archivo', accessorKey: 'filename' as const, cell: (item: FinanceInvoice) => <div><p className="font-medium">{item.filename}</p>{item.parse_error && <p className="max-w-sm whitespace-normal text-xs text-amber-700">{item.parse_error}</p>}</div> },
    { header: 'UUID', accessorKey: 'uuid' as const, cell: (item: FinanceInvoice) => <span className="font-mono text-xs">{item.uuid || '—'}</span> },
    { header: 'Emisor', accessorKey: 'issuer_rfc' as const },
    { header: 'Receptor', accessorKey: 'receiver_rfc' as const },
    { header: 'Total', accessorKey: 'total' as const, cell: (item: FinanceInvoice) => item.total == null ? '—' : money.format(item.total) },
    { header: 'Estatus', accessorKey: 'status' as const, cell: (item: FinanceInvoice) => <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold">{item.status}</span> },
    { header: 'Acción', accessorKey: (item: FinanceInvoice) => item.status, enableFiltering: false, cell: (item: FinanceInvoice) => <button disabled={!item.total || !item.issued_at || item.status === 'conciliada'} onClick={() => suggest(item)} className="rounded-lg border px-3 py-1.5 text-xs font-bold disabled:opacity-40">Sugerir</button> },
  ], []);
  async function suggest(invoice: FinanceInvoice) {
    const response = await getInvoiceSuggestions(invoice.id);
    setSuggestions({ invoice, items: response.items });
  }
  return <div className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">Facturas y conciliación</h2><p className="text-sm text-slate-500">El XML aporta datos CFDI; un PDF solo se conserva como evidencia y no acredita validez fiscal.</p></div><button onClick={onScan} className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white"><FileSearch className="h-4 w-4" />Indexar carpeta</button></div>
    {!folderAvailable && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">La carpeta configurada de facturas no está montada en este servidor.</div>}
    {items.length ? <DataTable data={items} columns={columns} filterMode="multi-select" className="max-h-[calc(100dvh-25rem)] overflow-auto rounded-xl" /> : <Empty>No hay facturas indexadas.</Empty>}
    {suggestions && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"><div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-6"><div className="flex justify-between"><div><h3 className="text-lg font-bold">Sugerencias de conciliación</h3><p className="text-sm text-slate-500">{suggestions.invoice.filename}</p></div><button onClick={() => setSuggestions(null)}><X /></button></div><div className="mt-4 space-y-2">{suggestions.items.length ? suggestions.items.map((item) => <div key={item.movement.id} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div><p className="font-semibold">{item.movement.descripcion_original}</p><p className="text-xs text-slate-500">{item.movement.fecha_operacion} · {money.format(item.movement.importe_neto)} · {item.rationale}</p></div><button onClick={async () => { await matchInvoice(suggestions.invoice.id, item.movement.id); setSuggestions(null); await onRefresh(); }} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white">Confirmar {item.confidence}%</button></div>) : <Empty>No hay candidatos con al menos 50% de confianza.</Empty>}</div></div></div>}
  </div>;
}

function CashFlow({ items, budgets, company, categories, onRefresh }: { items: Projection[]; budgets: Budget[]; company: Company; categories: FinanceCategories; onRefresh: () => Promise<void> }) {
  const [open, setOpen] = useState(false); const total = useMemo(() => items.reduce((sum, item) => sum + item.amount, 0), [items]);
  const budgetColumns = useMemo(() => [
    { header: 'Empresa', accessorKey: 'company' as const },
    { header: 'Mes', accessorKey: 'month' as const },
    { header: 'Categoría', accessorKey: 'category' as const },
    { header: 'Presupuesto', accessorKey: 'budget' as const, cell: (item: Budget) => money.format(item.budget) },
    { header: 'Real', accessorKey: 'actual' as const, cell: (item: Budget) => money.format(item.actual) },
    { header: 'Variación', accessorKey: 'variance' as const, cell: (item: Budget) => <span className={`font-semibold ${item.variance < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{money.format(item.variance)}</span> },
  ], []);
  return <div className="space-y-5"><div className="flex items-start justify-between"><div><h2 className="text-lg font-bold">Flujo futuro y presupuesto</h2><p className="text-sm text-slate-500">Real histórico más compromisos futuros. Las proyecciones nunca se mezclan con movimientos bancarios reales.</p></div><button disabled={company === 'CONSOLIDADO'} onClick={() => setOpen(true)} className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-40"><Plus className="h-4 w-4" />Proyección</button></div><Kpi label="Compromisos proyectados" value={money.format(total)} tone={total < 0 ? 'amber' : 'green'} />{items.length ? <div className="space-y-2">{items.map((item) => <div key={item.id} className="flex items-center justify-between rounded-xl border p-4"><div><p className="font-semibold">{item.concept}</p><p className="text-xs text-slate-500">{item.company} · {dateFormat.format(new Date(`${item.due_date}T12:00:00`))} · escenario {item.scenario}</p></div><div className="flex items-center gap-3"><span className={`font-bold ${item.amount < 0 ? 'text-red-600' : 'text-emerald-700'}`}>{money.format(item.amount)}</span><button onClick={async () => { await cancelProjection(item.id); await onRefresh(); }} title="Cancelar"><Trash2 className="h-4 w-4 text-slate-400" /></button></div></div>)}</div> : <Empty>No hay compromisos proyectados en los próximos 90 días.</Empty>}
    <section><h3 className="mb-2 font-bold">Presupuesto mensual vs. real</h3>{budgets.length ? <DataTable data={budgets} columns={budgetColumns} filterMode="multi-select" className="rounded-xl" /> : <Empty>{company === 'CONSOLIDADO' ? 'Selecciona TLA o TS para capturar presupuesto.' : <BudgetQuickForm company={company} categories={categories} onCreated={onRefresh} />}</Empty>}</section>
    {open && <ProjectionModal company={company as 'TLA' | 'TS'} onClose={() => setOpen(false)} onCreated={async () => { setOpen(false); await onRefresh(); }} />}
  </div>;
}

function BudgetQuickForm({ company, categories, onCreated }: { company: 'TLA' | 'TS'; categories: FinanceCategories; onCreated: () => Promise<void> }) {
  const [category, setCategory] = useState(''); const [amount, setAmount] = useState(''); const month = new Date().toISOString().slice(0, 7) + '-01';
  return <div className="w-full max-w-md"><p className="mb-3">Crea la primera partida del mes para {company}.</p><div className="flex gap-2"><select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Categoría del presupuesto" className="min-w-0 flex-1 rounded-lg border bg-white px-3 py-2 text-slate-900"><option value="">Selecciona categoría</option>{Object.keys(categories).map((value) => <option key={value} value={value}>{value}</option>)}</select><input value={amount} onChange={(e) => setAmount(e.target.value)} type="number" placeholder="Monto" className="w-28 rounded-lg border px-3 py-2 text-slate-900" /><button disabled={!category || !amount} onClick={async () => { await upsertBudget({ company, month, category, amount: Number(amount) }); await onCreated(); }} className="rounded-lg bg-emerald-600 px-3 py-2 font-bold text-white disabled:opacity-40">Guardar</button></div></div>;
}

function ProjectionModal({ company, onClose, onCreated }: { company: 'TLA' | 'TS'; onClose: () => void; onCreated: () => Promise<void> }) {
  const [concept, setConcept] = useState(''); const [dueDate, setDueDate] = useState(''); const [amount, setAmount] = useState('');
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"><div className="w-full max-w-lg rounded-2xl bg-white p-6"><div className="flex justify-between"><h2 className="text-lg font-bold">Nueva proyección · {company}</h2><button onClick={onClose}><X /></button></div><div className="mt-5 space-y-3"><input value={concept} onChange={(e) => setConcept(e.target.value)} placeholder="Concepto" className="w-full rounded-lg border px-3 py-2" /><input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="w-full rounded-lg border px-3 py-2" /><input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Importe (negativo para salida)" className="w-full rounded-lg border px-3 py-2" /></div><div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border px-4 py-2">Cancelar</button><button onClick={async () => { await createProjection({ company, concept, due_date: dueDate, amount: Number(amount), scenario: 'base' }); await onCreated(); }} disabled={!concept || !dueDate || !amount} className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white disabled:opacity-40">Crear</button></div></div></div>;
}

function Rules({ items, categories, onRefresh, setError }: { items: Rule[]; categories: FinanceCategories; onRefresh: () => Promise<void>; setError: (value: string) => void }) {
  const [open, setOpen] = useState(false); const [preview, setPreview] = useState<{ rule: Rule; total: number; conflicts: number } | null>(null);
  return <div className="space-y-4"><div className="flex justify-between"><div><h2 className="text-lg font-bold">Reglas de clasificación</h2><p className="text-sm text-slate-500">Previsualiza coincidencias y conflictos antes de aplicar. La fuente original no se modifica.</p></div><button onClick={() => setOpen(true)} className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-bold text-white"><Plus className="h-4 w-4" />Regla</button></div>{items.length ? <div className="space-y-2">{items.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"><div><p className="font-semibold">{item.priority}. {item.name}</p><p className="text-xs text-slate-500">{item.company || 'Todas'} · {item.field} {item.operator.replace('_', ' ')} “{item.value}” → {item.exclusion ? 'Excluir' : `${item.category}${item.subcategory ? ` / ${item.subcategory}` : ''}`}</p></div><div className="flex gap-2"><button onClick={async () => { const result = await previewRule(item.id); setPreview({ rule: item, total: result.total, conflicts: result.conflicts }); }} className="rounded-lg border px-3 py-1.5 text-xs font-bold">Previsualizar</button><button onClick={async () => { try { const result = await revertRule(item.id); setError(`Se restauraron ${result.restored} movimientos.`); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No hay una ejecución reversible'); } }} className="rounded-lg border px-3 py-1.5 text-xs font-bold">Revertir última</button><button onClick={async () => { await deleteRule(item.id); await onRefresh(); }} className="rounded-lg p-2 text-red-600"><Trash2 className="h-4 w-4" /></button></div></div>)}</div> : <Empty>No hay patrones de clasificación configurados.</Empty>}{open && <RuleModal categories={categories} onClose={() => setOpen(false)} onCreated={async () => { setOpen(false); await onRefresh(); }} />}{preview && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"><div className="w-full max-w-md rounded-2xl bg-white p-6"><h3 className="text-lg font-bold">Previsualización</h3><p className="mt-3 text-sm"><strong>{preview.total}</strong> movimientos coinciden; <strong>{preview.conflicts}</strong> ya tienen una categoría diferente.</p><p className="mt-2 text-xs text-slate-500">Aplicar actualiza la capa de clasificación y queda registrado en auditoría.</p><div className="mt-5 flex justify-end gap-2"><button onClick={() => setPreview(null)} className="rounded-lg border px-4 py-2">Cancelar</button><button onClick={async () => { try { const result = await applyRule(preview.rule.id); setPreview(null); setError(`Regla aplicada a ${result.updated} movimientos.`); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo aplicar'); } }} className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white">Aplicar</button></div></div></div>}</div>;
}

function RuleModal({ categories, onClose, onCreated }: { categories: FinanceCategories; onClose: () => void; onCreated: () => Promise<void> }) {
  const [name, setName] = useState('');
  const [value, setValue] = useState('');
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true); setError('');
    try {
      await createRule({ name, priority: 100, field: 'descripcion_original', operator: 'contiene', value, company: null, category, subcategory, enabled: true, exclusion: false });
      await onCreated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo crear la regla'); }
    finally { setSaving(false); }
  }

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4"><div className="w-full max-w-lg rounded-2xl bg-white p-6">
    <div className="flex justify-between"><h2 className="text-lg font-bold">Nueva regla</h2><button onClick={onClose} aria-label="Cerrar"><X /></button></div>
    <div className="mt-5 space-y-3"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nombre" className="w-full rounded-lg border px-3 py-2" /><input value={value} onChange={(event) => setValue(event.target.value)} placeholder="Texto contenido en la descripción original" className="w-full rounded-lg border px-3 py-2" /><ClassificationFields categories={categories} category={category} subcategory={subcategory} onCategoryChange={setCategory} onSubcategoryChange={setSubcategory} /></div>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border px-4 py-2">Cancelar</button><button onClick={save} disabled={saving || !name.trim() || !value.trim() || !category || !subcategory} className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white disabled:opacity-40">{saving ? 'Creando…' : 'Crear'}</button></div>
  </div></div>;
}

function UploadWizard({ onClose, onPublished }: { onClose: () => void; onPublished: () => Promise<void> }) {
  const [source, setSource] = useState('tla_amex');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ ingestion_id: string; filename: string; source_filename: string; rows: number; new_rows: number; duplicates: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
    <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl">
      <div className="flex items-start justify-between border-b p-6">
        <div><h2 className="text-xl font-bold">Carga guiada de estados</h2><p className="text-sm text-slate-500">Previsualiza, detecta duplicados y confirma antes de tocar el histórico canónico.</p></div>
        <button onClick={onClose} aria-label="Cerrar"><X /></button>
      </div>
      <div className="space-y-4 p-6">
        <ErrorMessage text={error} />
        <label className="block text-sm font-semibold">Fuente
          <select value={source} onChange={(event) => { setSource(event.target.value); setPreview(null); }} className="mt-1 w-full rounded-lg border px-3 py-2 font-normal">
            <option value="tla_amex">TLA · AMEX</option><option value="tla_bbva">TLA · BBVA</option><option value="tla_banorte">TLA · Banorte</option><option value="ts_bbva">TS · BBVA</option>
          </select>
        </label>
        <label className="block rounded-xl border-2 border-dashed border-slate-300 p-6 text-center"><Upload className="mx-auto h-7 w-7 text-slate-400" /><span className="mt-2 block text-sm font-semibold">{file?.name || 'Seleccionar CSV canónico o estado original'}</span><input type="file" accept=".csv,.pdf" className="sr-only" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); }} /></label>
        {preview && <div className="space-y-3"><div className="grid grid-cols-3 gap-3"><Kpi label="Filas" value={String(preview.rows)} /><Kpi label="Nuevas" value={String(preview.new_rows)} tone="green" /><Kpi label="Duplicadas" value={String(preview.duplicates)} tone={preview.duplicates ? 'amber' : 'green'} /></div><div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-slate-700"><p>Archivo de carga: <strong>{preview.filename}</strong></p><p>Fuente de movimientos: <strong>{preview.source_filename}</strong></p></div></div>}
        <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">Los PDF originales se preservan, pero solo se publican automáticamente cuando existe un parser validado para ese formato. El sistema nunca adivina movimientos bancarios.</div>
      </div>
      <div className="flex justify-end gap-2 border-t p-5">
        <button onClick={onClose} className="rounded-lg border px-4 py-2">Cancelar</button>
        {!preview ? <button disabled={!file || busy} onClick={async () => { if (!file) return; setBusy(true); setError(''); try { setPreview(await previewIngestion(source, file)); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo previsualizar'); } finally { setBusy(false); } }} className="rounded-lg bg-slate-900 px-4 py-2 font-bold text-white disabled:opacity-40">{busy ? 'Validando…' : 'Previsualizar'}</button> : <button disabled={busy || preview.duplicates > 0 || preview.new_rows === 0} onClick={async () => { setBusy(true); setError(''); try { await publishIngestion(preview.ingestion_id); await onPublished(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo publicar'); } finally { setBusy(false); } }} className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white disabled:opacity-40">Confirmar y publicar</button>}
      </div>
    </div>
  </div>;
}
