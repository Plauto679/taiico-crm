'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CalendarClock, CircleDollarSign, Plus, Target, TrendingUp, X } from 'lucide-react';
import { searchQuoteClients } from '@/modules/cotizaciones/service';
import {
  changeCommercialStage,
  createCommercialOpportunity,
  type CommercialConfig,
  type CommercialOpportunity,
  type CommercialPipeline,
  type QuoteClient,
} from '@/modules/gestion-comercial/service';

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
const priorityLabel = { low: 'Baja', medium: 'Media', high: 'Alta' } as const;

export function CommercialBoard({ initialPipeline, config }: { initialPipeline: CommercialPipeline; config: CommercialConfig }) {
  const [pipeline, setPipeline] = useState(initialPipeline);
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState('');
  const [error, setError] = useState('');

  async function move(opportunity: CommercialOpportunity, stageCode: string) {
    if (opportunity.stage.code === stageCode || moving) return;
    setMoving(opportunity.id); setError('');
    try {
      const updated = await changeCommercialStage(opportunity.id, stageCode);
      setPipeline((current) => {
        const expectedDelta = updated.expected_value - opportunity.expected_value;
        return {
          ...current,
          opportunities: current.opportunities.map((item) => item.id === updated.id ? updated : item),
          summary: {
            ...current.summary,
            expected_funnel: current.summary.expected_funnel + expectedDelta,
            projection: current.summary.projection + expectedDelta,
          },
        };
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message.replace(/^API Error:\s*/, '') : 'No fue posible cambiar la etapa');
    } finally { setMoving(''); }
  }

  const active = pipeline.opportunities.filter((item) => item.status === 'active');
  return <div className="flex min-h-0 flex-1 flex-col gap-4">
    <div className="grid flex-none gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Metric icon={Target} label="Oportunidades activas" value={String(pipeline.summary.active_opportunities)} />
      <Metric icon={CircleDollarSign} label="Venta pagada" value={money.format(pipeline.summary.paid_sales)} />
      <Metric icon={TrendingUp} label="Funnel potencial" value={money.format(pipeline.summary.potential_funnel)} />
      <Metric icon={TrendingUp} label="Venta esperada" value={money.format(pipeline.summary.expected_funnel)} />
      <Metric icon={Target} label="Proyección comercial" value={money.format(pipeline.summary.projection)} />
    </div>
    <div className="flex flex-none items-center justify-between gap-3">
      {error ? <p role="alert" className="rounded-lg bg-red-50 px-4 py-2 text-sm font-semibold text-red-700">{error}</p> : <span />}
      {config.can_operate && <button onClick={() => setCreating(true)} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2.5 font-semibold text-blue-700 shadow hover:bg-blue-50"><Plus className="h-5 w-5" />Nueva oportunidad</button>}
    </div>
    <div className="min-h-0 flex-1 overflow-x-auto overflow-y-hidden rounded-xl bg-slate-100/95 p-3 shadow-inner">
      <div className="flex h-full min-w-max gap-3">
        {pipeline.stages.map((stage) => {
          const cards = active.filter((item) => item.stage.code === stage.code);
          return <section key={stage.id} className="flex h-full w-[19rem] flex-col rounded-xl border border-slate-200 bg-slate-50"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const id = event.dataTransfer.getData('text/opportunity-id');
              const opportunity = active.find((item) => item.id === id);
              if (opportunity) void move(opportunity, stage.code);
            }}>
            <header className="flex items-start justify-between gap-2 border-b border-slate-200 px-3 py-3">
              <div><h2 className="font-bold text-slate-900">{stage.name}</h2><p className="text-xs text-slate-500">Conversión {stage.conversion_rate}%</p></div>
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700">{cards.length}</span>
            </header>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
              {cards.map((item) => <OpportunityCard key={item.id} opportunity={item} moving={moving === item.id} />)}
              {!cards.length && <p className="rounded-lg border border-dashed border-slate-300 px-3 py-8 text-center text-xs text-slate-400">Arrastra una oportunidad aquí</p>}
            </div>
          </section>;
        })}
      </div>
    </div>
    {creating && <OpportunityModal pipeline={pipeline} config={config} onClose={() => setCreating(false)} onCreated={(opportunity) => {
      setPipeline((current) => ({ ...current, opportunities: [...current.opportunities, opportunity], summary: {
        ...current.summary,
        active_opportunities: current.summary.active_opportunities + 1,
        potential_funnel: current.summary.potential_funnel + opportunity.potential_premium,
        expected_funnel: current.summary.expected_funnel + opportunity.expected_value,
        projection: current.summary.projection + opportunity.expected_value,
      } }));
      setCreating(false);
    }} />}
  </div>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Target; label: string; value: string }) {
  return <div className="rounded-xl border border-white/40 bg-white p-4 shadow"><div className="flex items-center gap-2 text-sm font-medium text-slate-500"><Icon className="h-4 w-4 text-blue-600" />{label}</div><p className="mt-2 text-2xl font-bold text-slate-900">{value}</p></div>;
}

function OpportunityCard({ opportunity, moving }: { opportunity: CommercialOpportunity; moving: boolean }) {
  const nextTask = opportunity.tasks.find((task) => task.status !== 'completed');
  return <article draggable={!moving} onDragStart={(event) => event.dataTransfer.setData('text/opportunity-id', opportunity.id)} className={`cursor-grab rounded-xl border bg-white p-4 shadow-sm transition hover:border-blue-300 hover:shadow ${moving ? 'opacity-50' : ''}`}>
    <div className="flex items-start justify-between gap-2"><h3 className="font-bold leading-tight text-slate-900">{opportunity.client_name}</h3><span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${opportunity.priority === 'high' ? 'bg-red-100 text-red-700' : opportunity.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>{priorityLabel[opportunity.priority]}</span></div>
    <p className="mt-1 text-sm text-slate-600">{opportunity.product_name}</p>
    <div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div><p className="text-slate-400">Prima potencial</p><p className="font-bold text-slate-800">{money.format(opportunity.potential_premium)}</p></div><div><p className="text-slate-400">Venta esperada</p><p className="font-bold text-blue-700">{money.format(opportunity.expected_value)}</p></div></div>
    <p className="mt-3 text-xs text-slate-500">{opportunity.owner_agent_name} · {opportunity.owner_promotoria}</p>
    {opportunity.quote_ids.length > 0 && <p className="mt-2 text-xs font-semibold text-emerald-700">{opportunity.quote_ids.length} cotización vinculada</p>}
    {nextTask && <div className="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-900"><p className="flex items-center gap-1 font-bold"><AlertTriangle className="h-3.5 w-3.5" />{nextTask.title}</p><p className="mt-1 text-amber-700">{nextTask.assigned_to || nextTask.responsible_role || 'Sin asignar'}</p></div>}
    {!nextTask && opportunity.next_activity_at && <p className="mt-3 flex items-center gap-1 text-xs text-slate-500"><CalendarClock className="h-3.5 w-3.5" />{new Date(opportunity.next_activity_at).toLocaleString('es-MX')}</p>}
  </article>;
}

function OpportunityModal({ pipeline, config, onClose, onCreated }: { pipeline: CommercialPipeline; config: CommercialConfig; onClose: () => void; onCreated: (value: CommercialOpportunity) => void }) {
  const [clientQuery, setClientQuery] = useState('');
  const [clients, setClients] = useState<QuoteClient[]>([]);
  const [client, setClient] = useState<QuoteClient | null>(null);
  const [newProspect, setNewProspect] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (client || newProspect || clientQuery.trim().length < 2) return;
    const timer = window.setTimeout(() => searchQuoteClients(clientQuery).then(setClients).catch(() => setClients([])), 250);
    return () => window.clearTimeout(timer);
  }, [client, clientQuery, newProspect]);
  const agentOptions = useMemo(() => config.agents.map((agent) => ({ ...agent, value: `${agent.rfc}|${agent.promotoria}` })), [config.agents]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError('');
    const form = new FormData(event.currentTarget);
    const agent = agentOptions.find((item) => item.value === form.get('agent'));
    const product = config.products.find((item) => item.id === form.get('product'));
    if (!agent) { setError('Selecciona al agente dueño'); setSaving(false); return; }
    try {
      const opportunity = await createCommercialOpportunity({
        client_id: client?.id,
        prospect_name: newProspect ? clientQuery.trim() : undefined,
        product_id: product?.id,
        product_name: product?.name || String(form.get('product_name') || 'Producto por definir'),
        business_line: product?.branch || String(form.get('business_line') || ''),
        owner_agent_rfc: agent.rfc,
        owner_agent_name: agent.name,
        owner_promotoria: agent.promotoria,
        potential_premium: Number(form.get('potential_premium') || 0),
        currency: 'MXN', stage_code: String(form.get('stage_code') || 'prospecting'),
        priority: String(form.get('priority') || 'medium') as 'low' | 'medium' | 'high',
        source: String(form.get('source') || ''), estimated_close_date: String(form.get('estimated_close_date') || '') || undefined,
        detected_need: String(form.get('detected_need') || ''), description: String(form.get('description') || ''),
      });
      onCreated(opportunity);
    } catch (cause) { setError(cause instanceof Error ? cause.message.replace(/^API Error:\s*/, '') : 'No fue posible crear la oportunidad'); }
    finally { setSaving(false); }
  }

  return <div className="fixed inset-0 z-[90] grid place-items-center overflow-y-auto bg-slate-950/50 p-4 backdrop-blur-sm"><form onSubmit={submit} className="my-6 w-full max-w-3xl rounded-2xl bg-white shadow-2xl">
    <header className="flex items-start justify-between border-b px-6 py-5"><div><h2 className="text-2xl font-bold text-slate-900">Nueva oportunidad</h2><p className="text-sm text-slate-500">Selecciona un cliente existente o registra un prospecto.</p></div><button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-slate-100"><X /></button></header>
    <div className="grid gap-4 p-6 sm:grid-cols-2">
      <label className="relative grid gap-1.5 text-sm font-semibold text-slate-700 sm:col-span-2">Cliente o prospecto<input value={client?.nombre || clientQuery} onChange={(event) => { setClient(null); setClientQuery(event.target.value); setNewProspect(false); setClients([]); }} required className="rounded-lg border border-slate-300 px-3 py-2.5 font-normal" />
        {clients.length > 0 && <div className="absolute left-0 right-0 top-full z-10 max-h-48 overflow-auto rounded-lg border bg-white shadow-xl">{clients.map((item) => <button type="button" key={item.id} onClick={() => { setClient(item); setClientQuery(item.nombre); setNewProspect(false); setClients([]); }} className="block w-full px-3 py-2 text-left font-normal hover:bg-blue-50">{item.nombre} <span className="text-xs text-slate-400">{item.rfc}</span></button>)}</div>}
      </label>
      {!client && clientQuery.trim().length >= 2 && <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2"><input type="checkbox" checked={newProspect} onChange={(event) => { setNewProspect(event.target.checked); setClients([]); }} />Registrar “{clientQuery.trim()}” como prospecto nuevo</label>}
      <SelectField label="Agente dueño" name="agent" required options={agentOptions.map((item) => ({ value: item.value, label: `${item.name} · ${item.promotoria}` }))} />
      <SelectField label="Producto" name="product" options={config.products.map((item) => ({ value: item.id, label: `${item.branch} · ${item.name}` }))} />
      <InputField label="Prima potencial" name="potential_premium" type="number" min="0" step="0.01" required />
      <SelectField label="Etapa" name="stage_code" options={pipeline.stages.map((item) => ({ value: item.code, label: `${item.name} (${item.conversion_rate}%)` }))} />
      <SelectField label="Prioridad" name="priority" options={[{ value: 'high', label: 'Alta' }, { value: 'medium', label: 'Media' }, { value: 'low', label: 'Baja' }]} />
      <InputField label="Fecha estimada de cierre" name="estimated_close_date" type="date" />
      <InputField label="Origen" name="source" placeholder="Referido, campaña, cartera…" />
      <InputField label="Necesidad detectada" name="detected_need" wide />
      <label className="grid gap-1.5 text-sm font-semibold text-slate-700 sm:col-span-2">Descripción<textarea name="description" rows={3} className="rounded-lg border border-slate-300 px-3 py-2.5 font-normal" /></label>
      {error && <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 sm:col-span-2">{error}</p>}
    </div>
    <footer className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 font-semibold text-slate-700">Cancelar</button><button disabled={saving || (!client && !newProspect)} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-50">{saving ? 'Guardando…' : 'Crear oportunidad'}</button></footer>
  </form></div>;
}

function InputField({ label, wide, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string; wide?: boolean }) { return <label className={`grid gap-1.5 text-sm font-semibold text-slate-700 ${wide ? 'sm:col-span-2' : ''}`}>{label}<input {...props} className="rounded-lg border border-slate-300 px-3 py-2.5 font-normal" /></label>; }
function SelectField({ label, options, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string; options: { value: string; label: string }[] }) { return <label className="grid gap-1.5 text-sm font-semibold text-slate-700">{label}<select {...props} className="rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal">{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>; }
