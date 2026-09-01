'use client';

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { CalendarClock, CheckCircle2, Clock3, MailCheck, PauseCircle, Save, Send, UsersRound } from 'lucide-react';
import {
  AutomaticMail,
  AutomaticMailDirectory,
  AutomaticMailUpdate,
  updateAutomaticMail,
} from '@/modules/automatic-mails/service';

const WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const CADENCE_LABELS = { daily: 'Diario', weekly: 'Semanal', monthly: 'Mensual' } as const;
const INPUT_CLASS = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100';

function emailsText(values: string[]): string {
  return values.join('\n');
}

function parseEmails(value: string): string[] {
  return Array.from(new Set(
    value
      .split(/[,;\n]+/)
      .map((item) => item.trim().toLocaleLowerCase('es-MX'))
      .filter(Boolean),
  ));
}

function scheduleLabel(item: AutomaticMail): string {
  const time = `${String(item.hour).padStart(2, '0')}:${String(item.minute).padStart(2, '0')}`;
  if (item.cadence === 'weekly') return `${WEEKDAYS[item.day_of_week ?? 0]} a las ${time}`;
  if (item.cadence === 'monthly') return `Día ${item.day_of_month ?? 1} de cada mes a las ${time}`;
  return `Todos los días a las ${time}`;
}

export function AutomaticMailsView({ initialDirectory }: { initialDirectory: AutomaticMailDirectory }) {
  const [automations, setAutomations] = useState(initialDirectory.automations);
  const [editingId, setEditingId] = useState<string | null>(null);
  const active = useMemo(() => automations.filter((item) => item.enabled).length, [automations]);

  function replace(item: AutomaticMail) {
    setAutomations((current) => current.map((candidate) => candidate.id === item.id ? item : candidate));
  }

  return <div className="flex h-full min-h-0 flex-col gap-6 overflow-y-auto p-5 sm:p-8">
    <div className="flex flex-wrap items-start justify-between gap-4 text-white">
      <div>
        <h1 className="flex items-center gap-3 text-3xl font-bold"><MailCheck className="h-8 w-8" /> Mails automáticos</h1>
        <p className="mt-2 max-w-3xl text-sm text-blue-100">Consulta y edita remitentes, destinatarios y periodicidad de los correos programados de TAIICO OS.</p>
      </div>
      <div className="rounded-xl border border-white/20 bg-white/10 px-5 py-3 text-right backdrop-blur">
        <p className="text-xs uppercase tracking-wide text-blue-100">Automatizaciones activas</p>
        <p className="text-2xl font-bold">{active} de {automations.length}</p>
      </div>
    </div>

    <div className="grid gap-5 xl:grid-cols-2">
      {automations.map((item) => <AutomaticMailCard
        key={item.id}
        item={item}
        canOperate={initialDirectory.can_operate}
        editing={editingId === item.id}
        onEdit={() => setEditingId(item.id)}
        onCancel={() => setEditingId(null)}
        onSaved={(saved) => { replace(saved); setEditingId(null); }}
      />)}
    </div>
  </div>;
}

function AutomaticMailCard({
  item,
  canOperate,
  editing,
  onEdit,
  onCancel,
  onSaved,
}: {
  item: AutomaticMail;
  canOperate: boolean;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSaved: (item: AutomaticMail) => void;
}) {
  const [draft, setDraft] = useState(item);
  const [recipients, setRecipients] = useState(emailsText(item.recipients));
  const [copies, setCopies] = useState(emailsText(item.cc_recipients));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function startEditing() {
    setDraft(item);
    setRecipients(emailsText(item.recipients));
    setCopies(emailsText(item.cc_recipients));
    setMessage('');
    setError('');
    onEdit();
  }

  async function save() {
    setBusy(true); setMessage(''); setError('');
    const payload: AutomaticMailUpdate = {
      enabled: draft.enabled,
      cadence: draft.cadence,
      hour: Number(draft.hour),
      minute: Number(draft.minute),
      timezone: draft.timezone,
      day_of_week: draft.cadence === 'weekly' ? (draft.day_of_week ?? 0) : null,
      day_of_month: draft.cadence === 'monthly' ? (draft.day_of_month ?? 1) : null,
      sender: draft.sender,
      recipients: item.recipient_mode === 'dynamic' ? [] : parseEmails(recipients),
      cc_recipients: parseEmails(copies),
    };
    try {
      const saved = await updateAutomaticMail(item.id, payload);
      setMessage('Configuración guardada. Se aplicará en la siguiente ejecución.');
      onSaved(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo guardar la configuración');
    } finally {
      setBusy(false);
    }
  }

  if (editing) return <article className="rounded-2xl border border-blue-200 bg-white shadow-xl">
    <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
      <div><h2 className="text-xl font-bold text-slate-900">{item.name}</h2><p className="mt-1 text-sm text-slate-500">{item.description}</p></div>
      <label className="flex shrink-0 items-center gap-2 text-sm font-semibold text-slate-700">
        <input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} className="h-5 w-5 accent-blue-600" /> Activo
      </label>
    </div>
    <div className="grid gap-4 p-5 sm:grid-cols-2">
      <Field label="Periodicidad">
        <select value={draft.cadence} onChange={(event) => setDraft({ ...draft, cadence: event.target.value as AutomaticMail['cadence'] })} className={INPUT_CLASS}>
          <option value="daily">Diario</option><option value="weekly">Semanal</option><option value="monthly">Mensual</option>
        </select>
      </Field>
      {draft.cadence === 'weekly' && <Field label="Día de la semana"><select value={draft.day_of_week ?? 0} onChange={(event) => setDraft({ ...draft, day_of_week: Number(event.target.value) })} className={INPUT_CLASS}>{WEEKDAYS.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></Field>}
      {draft.cadence === 'monthly' && <Field label="Día del mes"><input type="number" min={1} max={31} value={draft.day_of_month ?? 1} onChange={(event) => setDraft({ ...draft, day_of_month: Number(event.target.value) })} className={INPUT_CLASS} /></Field>}
      <Field label="Hora"><div className="grid grid-cols-2 gap-2"><input aria-label="Hora" type="number" min={0} max={23} value={draft.hour} onChange={(event) => setDraft({ ...draft, hour: Number(event.target.value) })} className={INPUT_CLASS} /><input aria-label="Minuto" type="number" min={0} max={59} value={draft.minute} onChange={(event) => setDraft({ ...draft, minute: Number(event.target.value) })} className={INPUT_CLASS} /></div></Field>
      <Field label="Zona horaria"><input value={draft.timezone} onChange={(event) => setDraft({ ...draft, timezone: event.target.value })} className={INPUT_CLASS} /></Field>
      <Field label="Remitente"><input type="email" value={draft.sender} onChange={(event) => setDraft({ ...draft, sender: event.target.value })} className={INPUT_CLASS} /></Field>
      {item.promotoria && <div className="sm:col-span-2"><Field label="Filtro fijo"><div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm font-semibold text-violet-800">Promotoría = {item.promotoria}</div></Field></div>}
      <div className="sm:col-span-2">
        <Field label="Destinatarios">
          {item.recipient_mode === 'dynamic'
            ? <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">{item.recipient_description}</div>
            : <textarea rows={4} value={recipients} onChange={(event) => setRecipients(event.target.value)} className={`${INPUT_CLASS} resize-y`} placeholder="Un correo por línea" />}
        </Field>
      </div>
      {(item.cc_description || item.cc_recipients.length > 0) && <div className="sm:col-span-2"><Field label="Copias (CC)"><p className="mb-1 text-xs text-slate-500">{item.cc_description}</p><textarea rows={3} value={copies} onChange={(event) => setCopies(event.target.value)} className={`${INPUT_CLASS} resize-y`} placeholder="Un correo por línea" /></Field></div>}
    </div>
    {(message || error) && <div className={`mx-5 mb-4 rounded-lg p-3 text-sm ${error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>{error || message}</div>}
    <div className="flex justify-end gap-3 border-t border-slate-200 p-4"><button type="button" onClick={onCancel} disabled={busy} className="rounded-lg px-4 py-2 font-semibold text-slate-600 hover:bg-slate-100">Cancelar</button><button type="button" onClick={save} disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"><Save className="h-4 w-4" /> {busy ? 'Guardando…' : 'Guardar'}</button></div>
  </article>;

  return <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
    <div className="flex items-start justify-between gap-4 p-5">
      <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-bold text-slate-900">{item.name}</h2><span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${item.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>{item.enabled ? <CheckCircle2 className="h-3.5 w-3.5" /> : <PauseCircle className="h-3.5 w-3.5" />}{item.enabled ? 'Activo' : 'Pausado'}</span></div><p className="mt-2 text-sm text-slate-500">{item.description}</p></div>
      {canOperate && <button type="button" onClick={startEditing} className="shrink-0 rounded-lg border border-blue-200 px-3 py-2 text-sm font-bold text-blue-700 hover:bg-blue-50">Editar</button>}
    </div>
    <div className="grid gap-px border-t border-slate-200 bg-slate-200 sm:grid-cols-2">
      <Detail icon={CalendarClock} label={CADENCE_LABELS[item.cadence]} value={scheduleLabel(item)} />
      <Detail icon={Send} label="Remitente" value={item.sender} />
      <Detail icon={UsersRound} label="Destinatarios" value={item.recipient_mode === 'dynamic' ? item.recipient_description : `${item.recipients.length} configurados`} />
      <Detail icon={Clock3} label="Zona horaria" value={item.timezone} />
      {item.promotoria && <Detail icon={UsersRound} label="Filtro fijo" value={`Promotoría = ${item.promotoria}`} />}
    </div>
    {item.recipient_mode === 'manual' && <div className="border-t border-slate-100 p-4"><p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Distribución actual</p><div className="flex flex-wrap gap-2">{item.recipients.map((email) => <span key={email} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700">{email}</span>)}</div>{item.cc_recipients.length > 0 && <><p className="mb-2 mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">Copias</p><div className="flex flex-wrap gap-2">{item.cc_recipients.map((email) => <span key={email} className="rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-700">{email}</span>)}</div></>}</div>}
  </article>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm font-semibold text-slate-700">{label}<div className="mt-1">{children}</div></label>;
}

function Detail({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="flex min-w-0 gap-3 bg-slate-50 p-4"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" /><div className="min-w-0"><p className="text-xs font-bold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-1 break-words text-sm font-medium text-slate-700">{value}</p></div></div>;
}
