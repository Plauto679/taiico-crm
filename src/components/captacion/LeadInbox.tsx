'use client';
import { useState } from 'react';
import Link from 'next/link';
import { fetchFromApi } from '@/lib/api';

type Lead = { id: string; name: string; phone: string; email: string; city: string; interest: string; source: string; stage: string; agent_name?: string; agent_rfc?: string; created_at: string; first_contact_due_at: string; next_followup_at?: string; note?: string; whatsapp_consent: boolean; attribution?: Record<string, string>; opportunity_id?: string };
export type LeadInboxData = { leads: Lead[]; can_edit: boolean; can_assign: boolean };
const stages: Record<string, string> = { new: 'Nuevo', contacted: 'Contactado', qualified: 'Calificado', closed: 'Gestión finalizada', lost: 'Descartado' };
const dateText = (v?: string) => v ? new Date(/Z$|[+-]\d\d:\d\d$/.test(v) ? v : `${v}Z`).toLocaleString('es-MX') : '—';
export function LeadInbox({ initial, kind }: { initial: LeadInboxData; kind: 'clientes' | 'agentes' }) {
  const [data, setData] = useState(initial);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Lead | null>(null);
  const [agents, setAgents] = useState<{ rfc: string; name: string }[]>([]);
  const [agent, setAgent] = useState('');
  const [stage, setStage] = useState('new');
  const [note, setNote] = useState('');
  const [next, setNext] = useState('');
  async function refresh() {
    setBusy(true); setError('');
    try { setData(await fetchFromApi(`/captacion/leads/${kind}`)); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function open(lead: Lead) {
    setSelected(lead); setStage(lead.stage); setAgent(lead.agent_rfc || ''); setNote(lead.note || ''); setError('');
    if (lead.next_followup_at) { const d = new Date(/Z$|[+-]\d\d:\d\d$/.test(lead.next_followup_at) ? lead.next_followup_at : `${lead.next_followup_at}Z`); setNext(new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)); } else setNext('');
    if (data.can_assign) try { const r = await fetchFromApi<{ agents: typeof agents }>('/captacion/agents'); setAgents(r.agents); } catch (e) { setError(String(e)); }
  }
  async function save() {
    if (!selected) return;
    setBusy(true); setError('');
    try {
      const payload = { stage, note, next_followup_at: next ? new Date(next).toISOString() : null, ...(agent && agent !== selected.agent_rfc ? { agent_rfc: agent } : {}) };
      const result = await fetchFromApi<{ lead: Lead }>(`/captacion/leads/${kind}/${selected.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      setData({ ...data, leads: data.leads.map(x => x.id === result.lead.id ? result.lead : x) }); setSelected(null);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const rows = data.leads.filter(x => !filter || `${x.name} ${x.phone} ${x.city} ${x.source} ${x.agent_name || ''}`.toLowerCase().includes(filter.toLowerCase()));
  const overdue = data.leads.filter(x => x.stage === 'new' && new Date(`${x.first_contact_due_at}Z`) < new Date()).length;
  return <div className="h-full overflow-auto p-5 md:p-8 text-white">
    <div className="flex flex-wrap justify-between gap-4"><div><h1 className="text-3xl font-bold">Leads de {kind === 'clientes' ? 'clientes' : 'nuevos agentes'}</h1><p className="mt-2 text-blue-100">Taiico · Solicitudes web y redes sociales</p></div><Link className="underline" href={kind === 'clientes' ? '/gestion-comercial' : '/recluta'}>Volver al módulo</Link></div>
    <div className="my-6 flex flex-wrap gap-4"><div className="rounded-xl bg-white/10 p-4">{data.leads.length} solicitudes visibles</div><div className="rounded-xl bg-white/10 p-4">{data.leads.filter(x => x.stage === 'new').length} nuevas</div><div className="rounded-xl bg-white/10 p-4">{overdue} sin primer contacto en 24 h</div></div>
    <p className="mb-4 text-sm text-blue-100">Objetivo interno: primer contacto en un día hábil. La alerta de 24 h es orientativa e incluye fines de semana. Hasta 500 solicitudes recientes. El cierre de venta se registra en Gestión Comercial.</p>
    <div className="mb-4 flex gap-3"><input className="flex-1 rounded-lg bg-white p-3 text-slate-900" placeholder="Buscar por nombre, teléfono, ciudad, origen o agente" aria-label="Buscar leads" value={filter} onChange={e => setFilter(e.target.value)} /><button disabled={busy} className="rounded-lg border px-4 disabled:opacity-50" onClick={refresh}>Actualizar</button></div>
    {error && <p role="alert" className="my-3 rounded bg-red-100 p-3 text-red-900">{error}</p>}
    <div className="overflow-x-auto rounded-xl bg-white text-slate-900"><table className="w-full text-left text-sm"><thead className="bg-slate-100"><tr>{['Contacto', 'Interés / ciudad', 'Origen', 'Responsable', 'Estado', 'Seguimiento', ''].map((h,i) => <th className="p-4" key={i}>{h}</th>)}</tr></thead><tbody>{rows.map(lead => <tr key={lead.id} className="border-t"><td className="p-4"><strong>{lead.name}</strong><br /><a className="text-blue-700" href={`tel:${lead.phone}`}>{lead.phone}</a><br />{lead.email}<br /><span className="text-xs text-slate-500">Recibido {dateText(lead.created_at)}</span></td><td className="p-4">{lead.interest}<br />{lead.city}</td><td className="p-4">{lead.source}<br /><span className="text-xs">{lead.attribution?.utm_campaign}<br />{lead.attribution?.utm_content}</span></td><td className="p-4">{lead.agent_name || (kind === 'clientes' ? 'Mesa Taiico · por asignar' : 'Reclutamiento Taiico')}</td><td className="p-4">{stages[lead.stage] || lead.stage}</td><td className="p-4">{dateText(lead.next_followup_at)}<br />{lead.note}</td><td className="p-4">{data.can_edit && <button className="rounded bg-[#34587c] px-3 py-2 text-white" onClick={() => open(lead)}>Gestionar</button>}</td></tr>)}</tbody></table>{!rows.length && <p className="p-8 text-center">Aún no hay solicitudes en esta bandeja.</p>}</div>
    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"><section role="dialog" aria-modal="true" aria-labelledby="lead-title" className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-6 text-slate-900"><h2 id="lead-title" className="text-xl font-bold">{selected.name}</h2><p className="my-3 text-sm">Contacto autorizado · WhatsApp: {selected.whatsapp_consent ? 'sí autorizado' : 'no autorizado'}</p><label className="block my-3">Estado<select className="mt-1 w-full rounded border p-2" value={stage} onChange={e => setStage(e.target.value)}>{Object.entries(stages).map(([v,t]) => <option value={v} key={v}>{t}</option>)}</select></label>{data.can_assign && <label className="block my-3">Agente de Taiico<select className="mt-1 w-full rounded border p-2" value={agent} onChange={e => setAgent(e.target.value)}><option value="">Sin nueva asignación</option>{agents.map(a => <option value={a.rfc} key={a.rfc}>{a.name}</option>)}</select></label>}<label className="block my-3">Próximo seguimiento (tu hora local)<input className="mt-1 w-full rounded border p-2" type="datetime-local" value={next} onChange={e => setNext(e.target.value)} /></label><label className="block my-3">Nota de seguimiento<textarea className="mt-1 w-full rounded border p-2" maxLength={2000} value={note} onChange={e => setNote(e.target.value)} /></label>{error && <p role="alert" className="text-red-700">{error}</p>}<div className="mt-5 flex justify-end gap-3"><button disabled={busy} onClick={() => setSelected(null)}>Cancelar</button><button disabled={busy} className="rounded bg-[#34587c] px-5 py-2 text-white disabled:opacity-50" onClick={save}>{busy ? 'Guardando…' : 'Guardar'}</button></div></section></div>}
  </div>;
}
