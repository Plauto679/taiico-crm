'use client';

import { useMemo, useState } from 'react';
import { ExternalLink, RefreshCw, Search, ShieldCheck, X } from 'lucide-react';
import { AuditLogEntry, syncAuditLogs } from '@/modules/logs/service';

const MODULE_LABELS: Record<string, string> = {
  accesos: 'Accesos', base_loads: 'Carga de bases', carga_bases: 'Carga de bases',
  cartera: 'Cartera', clientes: 'Clientes', cobranza: 'Cobranza', cotizaciones: 'Cotizaciones',
  pendientes: 'Pendientes', recluta: 'Recluta', renovaciones: 'Renovaciones', configuracion_mail: 'Configuración de Mail',
};

export function LogsView({ initialLogs, driveFolderUrl }: { initialLogs: AuditLogEntry[]; driveFolderUrl: string }) {
  const [logs] = useState(initialLogs);
  const [query, setQuery] = useState('');
  const [module, setModule] = useState('');
  const [outcome, setOutcome] = useState('');
  const [selected, setSelected] = useState<AuditLogEntry | null>(null);
  const [syncing, setSyncing] = useState(false);

  const modules = useMemo(() => [...new Set(logs.map((log) => log.module))].sort(), [logs]);
  const filtered = useMemo(() => logs.filter((log) => {
    const text = `${log.username} ${log.action} ${log.entity_id || ''} ${log.endpoint}`.toLocaleLowerCase('es');
    return (!query || text.includes(query.toLocaleLowerCase('es'))) && (!module || log.module === module) && (!outcome || log.outcome === outcome);
  }), [logs, query, module, outcome]);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await syncAuditLogs();
      if (!result.success) throw new Error('No se pudo completar el respaldo');
      alert('El archivo mensual de auditoría quedó actualizado en Google Drive.');
    } catch (error) {
      alert(error instanceof Error ? error.message : 'No se pudo sincronizar');
    } finally {
      setSyncing(false);
    }
  }

  return <div className="flex h-full min-h-0 flex-col gap-4 p-8">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><h1 className="text-3xl font-bold text-white">Logs</h1><p className="mt-1 text-blue-100">Bitácora de cambios y acciones realizadas en el CRM.</p></div>
      <div className="flex gap-2">
        <a href={driveFolderUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-white/40 px-4 py-2 font-medium text-white hover:bg-white/10"><ExternalLink className="h-4 w-4" />Abrir carpeta Logs</a>
        <button onClick={handleSync} disabled={syncing} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 font-semibold text-blue-700 disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />Respaldar ahora</button>
      </div>
    </div>

    <div className="grid gap-3 rounded-xl bg-white p-4 shadow md:grid-cols-[1fr_220px_180px_auto]">
      <label className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Usuario, acción, registro o ruta" className="w-full rounded-lg border py-2 pl-9 pr-3 text-slate-900" /></label>
      <select value={module} onChange={(e) => setModule(e.target.value)} className="rounded-lg border px-3 py-2 text-slate-900"><option value="">Todos los módulos</option>{modules.map((item) => <option key={item} value={item}>{MODULE_LABELS[item] || item}</option>)}</select>
      <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className="rounded-lg border px-3 py-2 text-slate-900"><option value="">Todos los resultados</option><option value="exitoso">Exitosos</option><option value="error">Con error</option></select>
      <div className="flex items-center justify-end whitespace-nowrap font-medium text-slate-600">{filtered.length} eventos</div>
    </div>

    <div className="min-h-0 flex-1 overflow-auto rounded-xl bg-white shadow">
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Fecha</th><th className="px-4 py-3">Usuario</th><th className="px-4 py-3">Módulo</th><th className="px-4 py-3">Acción</th><th className="px-4 py-3">Registro</th><th className="px-4 py-3">Resultado</th></tr></thead>
        <tbody className="divide-y">{filtered.map((log) => <tr key={log.id} onClick={() => setSelected(log)} className="cursor-pointer text-slate-700 hover:bg-blue-50"><td className="whitespace-nowrap px-4 py-3">{new Date(log.occurred_at + 'Z').toLocaleString('es-MX')}</td><td className="px-4 py-3 font-medium">{log.username}</td><td className="px-4 py-3">{MODULE_LABELS[log.module] || log.module}</td><td className="px-4 py-3">{log.action}</td><td className="px-4 py-3">{log.entity_id || '—'}</td><td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${log.outcome === 'exitoso' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{log.outcome}</span></td></tr>)}</tbody>
      </table>
      {!filtered.length && <div className="p-12 text-center text-slate-500"><ShieldCheck className="mx-auto mb-3 h-10 w-10" />No hay eventos que coincidan con los filtros.</div>}
    </div>

    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"><div className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-xl bg-white p-6 shadow-xl"><div className="flex items-start justify-between"><div><h2 className="text-xl font-bold text-slate-900">Detalle del evento</h2><p className="text-sm text-slate-500">{selected.id}</p></div><button onClick={() => setSelected(null)}><X className="h-6 w-6 text-slate-500" /></button></div><dl className="mt-5 grid gap-4 sm:grid-cols-2">{[['Usuario', selected.username], ['Fecha', new Date(selected.occurred_at + 'Z').toLocaleString('es-MX')], ['Módulo', MODULE_LABELS[selected.module] || selected.module], ['Resultado', `${selected.outcome} · HTTP ${selected.status_code}`], ['Acción', selected.action], ['Registro', selected.entity_id || '—'], ['Método', selected.http_method], ['Ruta', selected.endpoint], ['IP', selected.ip_address || '—']].map(([label, value]) => <div key={label}><dt className="text-xs font-semibold uppercase text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-800">{value}</dd></div>)}</dl><div className="mt-5"><h3 className="text-xs font-semibold uppercase text-slate-500">Datos modificados</h3><pre className="mt-2 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(selected.changes, null, 2)}</pre></div></div></div>}
  </div>;
}
