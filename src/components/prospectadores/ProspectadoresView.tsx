'use client';

import { useMemo, useState } from 'react';
import { BadgeCheck, BriefcaseBusiness, Combine, FileCheck2, Plus, Search, UserRoundSearch, X } from 'lucide-react';
import { createProspector, mergeProspector, migrateCarteraProspectors, updateProspector, type MigrationPreview, type Prospector, type ProspectorInput, type ProspectorSummary } from '@/modules/prospectadores/service';

const EMPTY: ProspectorInput = { name: '', rfc: '', email: '', additional_emails: [], payment_scheme: 'factura', is_active: true, linked_username: '' };

export function ProspectadoresView({ initialProspectors, initialSummary, migration }: { initialProspectors: Prospector[]; initialSummary: ProspectorSummary; migration: MigrationPreview }) {
  const [rows, setRows] = useState(initialProspectors);
  const [summary, setSummary] = useState(initialSummary);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Prospector | null | undefined>(undefined);
  const [form, setForm] = useState<ProspectorInput>(EMPTY);
  const [mergeTargetId, setMergeTargetId] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const filtered = useMemo(() => rows.filter((row) => `${row.name} ${row.rfc} ${row.email}`.toLowerCase().includes(search.toLowerCase())), [rows, search]);

  function open(row?: Prospector) {
    setEditing(row || null);
    setForm(row ? { name: row.name, rfc: row.rfc, email: row.email, additional_emails: row.additional_emails, payment_scheme: row.payment_scheme, is_active: row.is_active, linked_username: row.linked_username } : EMPTY);
    setMergeTargetId('');
    setMessage('');
  }

  async function save() {
    setBusy(true); setMessage('');
    try {
      const result = editing ? await updateProspector(editing.id, form) : await createProspector(form);
      setRows((current) => editing ? current.map((row) => row.id === editing.id ? { ...result.prospector, assignment_count: row.assignment_count } : row) : [...current, result.prospector].sort((a, b) => a.name.localeCompare(b.name)));
      setSummary((current) => ({ ...current, total: current.total + (editing ? 0 : 1), active: current.active + (editing ? Number(result.prospector.is_active) - Number(editing.is_active) : Number(result.prospector.is_active)) }));
      setEditing(undefined);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo guardar'); }
    finally { setBusy(false); }
  }

  async function migrate() {
    if (!confirm(`Se crearán asignaciones formales para ${migration.policies_pending} pólizas pendientes. ¿Continuar?`)) return;
    setBusy(true);
    try {
      const result = await migrateCarteraProspectors();
      setMessage(`Migración lista: ${result.created_prospectors} prospectadores y ${result.created_assignments} asignaciones creadas.`);
      window.location.reload();
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo migrar'); setBusy(false); }
  }

  async function consolidate() {
    if (!editing || !mergeTargetId) return;
    const target = rows.find((row) => row.id === mergeTargetId);
    if (!target || !confirm(`Se transferirán todas las pólizas y saldos de “${editing.name}” a “${target.name}” y se eliminará el registro duplicado. ¿Continuar?`)) return;
    setBusy(true); setMessage('');
    try {
      const result = await mergeProspector(editing.id, target.id);
      setRows((current) => current
        .filter((row) => row.id !== editing.id)
        .map((row) => row.id === target.id ? { ...row, assignment_count: row.assignment_count + editing.assignment_count } : row));
      setSummary((current) => ({
        ...current,
        total: current.total - 1,
        active: current.active - Number(editing.is_active),
        with_assignments: current.with_assignments - Number(editing.assignment_count > 0 && target.assignment_count > 0),
      }));
      setEditing(undefined);
      setMessage(`Prospectadores consolidados: ${result.moved_assignments} asignaciones transferidas a ${result.target_name}.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudieron consolidar los prospectadores'); }
    finally { setBusy(false); }
  }

  return <div className="h-full overflow-y-auto p-4 md:p-8">
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-3xl font-bold text-white">Prospectadores</h1><p className="mt-1 text-blue-100">Catálogo maestro, esquema de pago y pólizas asignadas.</p></div><div className="flex gap-2"><button disabled={busy || migration.policies_pending === 0} onClick={migrate} className="rounded-xl border border-white/30 px-4 py-3 font-semibold text-white disabled:opacity-50">Migrar desde Cartera ({migration.policies_pending})</button><button onClick={() => open()} className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 font-semibold text-blue-700"><Plus className="h-5 w-5" />Registrar prospectador</button></div></div>
      {message && <div className="rounded-xl bg-emerald-50 p-4 text-sm font-medium text-emerald-800">{message}</div>}
      <div className="grid gap-4 sm:grid-cols-4">{[[UserRoundSearch,'Registrados',summary.total],[BadgeCheck,'Activos',summary.active],[BriefcaseBusiness,'Con cartera',summary.with_assignments],[FileCheck2,'Asignaciones',summary.active_assignments]].map(([Icon,label,value]) => { const C = Icon as typeof UserRoundSearch; return <div key={String(label)} className="flex items-center gap-4 rounded-xl bg-white p-5 shadow"><div className="rounded-full bg-blue-100 p-3 text-blue-700"><C /></div><div><p className="text-sm text-slate-500">{String(label)}</p><p className="text-2xl font-bold text-slate-900">{String(value)}</p></div></div>})}</div>
      <div className="overflow-hidden rounded-xl bg-white shadow"><div className="flex items-center gap-3 border-b p-4"><Search className="text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por nombre, RFC o correo..." className="w-full bg-white text-slate-900 outline-none placeholder:text-slate-400" /></div><div className="overflow-x-auto"><table className="w-full text-left"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-4">Prospectador</th><th className="p-4">RFC</th><th className="p-4">Esquema</th><th className="p-4">Pólizas asignadas</th><th className="p-4">Estatus</th></tr></thead><tbody className="divide-y">{filtered.map((row) => <tr key={row.id} onClick={() => open(row)} className="cursor-pointer hover:bg-blue-50"><td className="p-4"><p className="font-semibold text-slate-900">{row.name}</p><p className="text-sm text-slate-500">{row.email || 'Sin correo'}</p></td><td className="p-4 text-slate-700">{row.rfc || '—'}</td><td className="p-4 text-slate-700">{row.payment_scheme === 'factura' ? 'Factura' : 'Asimilados a salarios'}</td><td className="p-4 font-semibold text-slate-800">{row.assignment_count}</td><td className="p-4"><span className={`rounded-full px-3 py-1 text-xs font-semibold ${row.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span></td></tr>)}</tbody></table></div></div>
    </div>
    {editing !== undefined && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><div className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white text-slate-900 shadow-2xl"><div className="flex items-center justify-between border-b p-5"><div><h2 className="text-xl font-bold text-slate-900">{editing ? 'Editar' : 'Registrar'} prospectador</h2><p className="text-sm text-slate-500">El esquema define si requiere factura antes del pago.</p></div><button onClick={() => setEditing(undefined)} className="rounded-full p-2 text-slate-600 hover:bg-slate-100"><X /></button></div><div className="grid gap-4 p-5 sm:grid-cols-2"><label className="sm:col-span-2 text-sm font-semibold text-slate-700">Nombre<input className="mt-1 w-full rounded-lg border bg-white p-3 font-normal text-slate-900" value={form.name} onChange={(e) => setForm({...form,name:e.target.value})}/></label><label className="text-sm font-semibold text-slate-700">RFC<input className="mt-1 w-full rounded-lg border bg-white p-3 font-normal text-slate-900" value={form.rfc || ''} onChange={(e) => setForm({...form,rfc:e.target.value})}/></label><label className="text-sm font-semibold text-slate-700">Correo<input type="email" className="mt-1 w-full rounded-lg border bg-white p-3 font-normal text-slate-900" value={form.email || ''} onChange={(e) => setForm({...form,email:e.target.value})}/></label><label className="text-sm font-semibold text-slate-700">Esquema<select className="mt-1 w-full rounded-lg border bg-white p-3 font-normal text-slate-900" value={form.payment_scheme} onChange={(e) => setForm({...form,payment_scheme:e.target.value as ProspectorInput['payment_scheme']})}><option value="factura">Factura</option><option value="asimilados_salarios">Asimilados a salarios</option></select></label><label className="flex items-center gap-2 pt-7 text-sm font-semibold text-slate-700"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({...form,is_active:e.target.checked})}/> Prospectador activo</label>{editing && <div className="sm:col-span-2 rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="flex items-center gap-2 font-semibold text-slate-900"><Combine className="h-5 w-5 text-amber-700"/>Consolidar registro duplicado</div><p className="mt-1 text-sm text-slate-600">Transfiere sus pólizas y saldos al prospectador principal y elimina este duplicado.</p><div className="mt-3 flex flex-col gap-2 sm:flex-row"><select value={mergeTargetId} onChange={(event)=>setMergeTargetId(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-amber-300 bg-white px-3 py-2.5 text-slate-900"><option value="">Seleccionar prospectador principal…</option>{rows.filter((row)=>row.id !== editing.id).map((row)=><option key={row.id} value={row.id}>{row.name} · {row.assignment_count} pólizas</option>)}</select><button disabled={busy || !mergeTargetId} onClick={consolidate} className="rounded-lg bg-amber-700 px-4 py-2.5 font-semibold text-white hover:bg-amber-800 disabled:opacity-50">Consolidar</button></div></div>}{message && <p className="sm:col-span-2 text-sm text-red-600">{message}</p>}</div><div className="flex justify-end gap-2 border-t bg-slate-50 p-5"><button onClick={() => setEditing(undefined)} className="rounded-lg border border-slate-300 bg-slate-200 px-5 py-2.5 font-semibold text-slate-800 hover:bg-slate-300">Cancelar</button><button disabled={busy || !form.name.trim()} onClick={save} className="rounded-lg bg-blue-700 px-5 py-2.5 font-semibold text-white hover:bg-blue-800 disabled:opacity-50">Guardar</button></div></div></div>}
  </div>;
}
