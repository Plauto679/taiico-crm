'use client';

import { useState } from 'react';
import { CheckCircle2, Clock3, ExternalLink } from 'lucide-react';
import type { CommercialPendingData, CommercialPendingTask } from '@/lib/types/pendientes';
import { updateCommercialPending } from '@/modules/pendientes/service';
import { SmartLink } from '@/components/navigation/SmartLink';

const statusLabels = { pending: 'Pendiente', in_progress: 'En proceso', completed: 'Completado' };

export function CommercialPendingPanel({ initialData, canOperate }: { initialData: CommercialPendingData; canOperate: boolean }) {
  const [tasks, setTasks] = useState(initialData.rows);
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');

  async function setStatus(task: CommercialPendingTask, status: CommercialPendingTask['status']) {
    setSaving(task.id); setError('');
    try {
      const response = await updateCommercialPending(task.id, status);
      setTasks((current) => current.map((item) => item.id === task.id ? response.task : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message.replace(/^API Error:\s*/, '') : 'No fue posible actualizar el pendiente');
    } finally { setSaving(''); }
  }

  return <div className="min-h-0 flex-1 overflow-auto rounded-lg bg-white shadow">
    {error && <p role="alert" className="m-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
    <div className="divide-y divide-slate-100">
      {tasks.map((task) => <article key={task.id} className="grid gap-3 p-4 hover:bg-slate-50 md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)_auto] md:items-center">
        <div><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold text-slate-900">{task.title}</h3>{task.blocks_stage_change && task.status !== 'completed' && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">Bloquea avance</span>}</div><p className="mt-1 text-sm text-slate-600">{task.client_name} · {task.product_name}</p><p className="mt-1 text-xs text-slate-400">{task.stage_name} · Agente dueño: {task.owner_agent_name}</p></div>
        <div className="text-sm"><p className="font-semibold text-slate-700">{task.assigned_to || task.responsible_role || 'Sin asignar'}</p><p className="mt-1 flex items-center gap-1 text-xs text-slate-500"><Clock3 className="h-3.5 w-3.5" />{task.due_date ? new Date(task.due_date).toLocaleDateString('es-MX') : 'Sin fecha compromiso'}</p></div>
        <div className="flex items-center gap-2"><SmartLink href={`/gestion-comercial?opportunity=${encodeURIComponent(task.opportunity_id)}`} className="rounded-lg border p-2 text-blue-700 hover:bg-blue-50" title="Ver oportunidad"><ExternalLink className="h-4 w-4" /></SmartLink>{canOperate && task.status !== 'completed' && <button disabled={saving === task.id} onClick={() => void setStatus(task, 'completed')} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"><CheckCircle2 className="h-4 w-4" />Completar</button>}<span className={`rounded-full px-3 py-1 text-xs font-semibold ${task.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : task.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>{statusLabels[task.status]}</span></div>
      </article>)}
      {!tasks.length && <div className="px-6 py-20 text-center text-slate-500"><CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-400" /><p className="font-semibold">No hay pendientes comerciales.</p></div>}
    </div>
  </div>;
}
