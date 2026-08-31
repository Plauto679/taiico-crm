'use client';

import { useMemo, useState } from 'react';
import { BadgeCheck, ExternalLink, KeyRound, Plus, Search, UserRoundCog, X } from 'lucide-react';
import {
  Agent,
  AgentDirectory,
  AgentInput,
  createAgent,
  updateAgent,
} from '@/modules/agentes/service';

const EMPTY_AGENT: AgentInput = {
  nombres: '',
  apellido_paterno: '',
  apellido_materno: '',
  clave_arranque: '',
  clave_definitiva: '',
  promotoria: '',
  rfc: '',
  inicio_vigencia_cedula: '',
  fin_vigencia_cedula: '',
  clasificacion_comercial: '',
  estatus_met: '',
};

export function AgentsView({ initialDirectory }: { initialDirectory: AgentDirectory }) {
  const [directory, setDirectory] = useState(initialDirectory);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Agent | null>(null);
  const [form, setForm] = useState<AgentInput>(EMPTY_AGENT);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('es');
    if (!query) return directory.agents;
    return directory.agents.filter((agent) => [
      agent.nombre,
      agent.rfc,
      agent.clave_arranque,
      agent.clave_definitiva,
      agent.promotoria,
      agent.clasificacion_comercial,
      agent.estatus_met,
    ].some((value) => value.toLocaleLowerCase('es').includes(query)));
  }, [directory.agents, search]);

  const active = directory.agents.filter((agent) => isActiveStatus(agent.estatus_met)).length;
  const withoutDefinitiveKey = directory.agents.filter((agent) => !agent.clave_definitiva).length;

  function openAgent(agent?: Agent) {
    if (!directory.can_operate) return;
    setEditing(agent || null);
    setForm(agent ? {
      nombres: agent.nombres,
      apellido_paterno: agent.apellido_paterno,
      apellido_materno: agent.apellido_materno,
      clave_arranque: agent.clave_arranque,
      clave_definitiva: agent.clave_definitiva,
      promotoria: agent.promotoria,
      rfc: agent.rfc,
      inicio_vigencia_cedula: agent.inicio_vigencia_cedula,
      fin_vigencia_cedula: agent.fin_vigencia_cedula,
      clasificacion_comercial: agent.clasificacion_comercial,
      estatus_met: agent.estatus_met,
    } : EMPTY_AGENT);
    setError('');
    setModalOpen(true);
  }

  async function save() {
    if (!form.nombres.trim() || !form.promotoria.trim()) {
      setError('Nombre(s) y Promotoría son obligatorios.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const updated = editing
        ? await updateAgent(editing, form, directory.version)
        : await createAgent(form, directory.version);
      setDirectory(updated);
      setModalOpen(false);
    } catch (reason) {
      setError(reason instanceof Error
        ? reason.message.replace('API Error: ', '')
        : 'No se pudo guardar el agente');
    } finally {
      setSaving(false);
    }
  }

  return <div className="flex h-full min-h-0 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold text-white">Agentes</h1>
        <p className="mt-1 text-blue-100">Directorio, claves y vigencia de cédula de agentes MetLife.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <a href={directory.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-white/40 px-4 py-2 font-semibold text-white hover:bg-white/10">
          <ExternalLink className="h-4 w-4" />Abrir fuente
        </a>
        {directory.can_operate && <button onClick={() => openAgent()} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 font-semibold text-blue-700 shadow hover:bg-blue-50">
          <Plus className="h-4 w-4" />Registrar agente
        </button>}
      </div>
    </div>

    <div className="grid gap-4 sm:grid-cols-3">
      <Summary icon={UserRoundCog} label="Agentes registrados" value={directory.agents.length} />
      <Summary icon={BadgeCheck} label="Estatus activo" value={active} />
      <Summary icon={KeyRound} label="Sin clave definitiva" value={withoutDefinitiveKey} />
    </div>

    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
      <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre, RFC, clave, promotoría o estatus..." className="w-full rounded-xl border border-white/20 bg-white py-3 pl-10 pr-4 text-slate-900 shadow outline-none focus:ring-2 focus:ring-blue-300" />
    </div>

    <div className="min-h-[360px] overflow-auto rounded-xl bg-white shadow">
      <table className="min-w-[1450px] w-full text-left text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>{['Agente', 'Clave arranque', 'Clave definitiva', 'Promotoría', 'RFC', 'Inicio vigencia cédula', 'Fin vigencia cédula', 'Clasificación comercial', 'Estatus Met'].map((heading) => <th key={heading} className="whitespace-nowrap px-4 py-3">{heading}</th>)}</tr>
        </thead>
        <tbody className="divide-y">
          {filtered.map((agent) => <tr key={agent.row_number} onClick={() => openAgent(agent)} className={`text-slate-700 ${directory.can_operate ? 'cursor-pointer hover:bg-blue-50' : ''}`}>
            <td className="px-4 py-3 font-semibold text-slate-900">{agent.nombre || '—'}</td>
            <td className="px-4 py-3 font-mono">{agent.clave_arranque || '—'}</td>
            <td className="px-4 py-3 font-mono">{agent.clave_definitiva || '—'}</td>
            <td className="px-4 py-3">{agent.promotoria || '—'}</td>
            <td className="px-4 py-3 font-mono">{agent.rfc || '—'}</td>
            <td className="px-4 py-3">{formatDate(agent.inicio_vigencia_cedula)}</td>
            <td className="px-4 py-3">{formatDate(agent.fin_vigencia_cedula)}</td>
            <td className="px-4 py-3">{agent.clasificacion_comercial || '—'}</td>
            <td className="px-4 py-3"><Status value={agent.estatus_met} /></td>
          </tr>)}
        </tbody>
      </table>
      {!filtered.length && <div className="p-12 text-center text-slate-500">No se encontraron agentes con esos criterios.</div>}
    </div>

    {modalOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-3 sm:p-6">
      <div className="max-h-[94vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white p-5">
          <div><h2 className="text-xl font-bold text-slate-900">{editing ? 'Editar agente' : 'Registrar agente'}</h2><p className="mt-1 text-sm text-slate-500">La información se guardará en la base compartida de agentes MetLife.</p></div>
          <button onClick={() => setModalOpen(false)} aria-label="Cerrar"><X className="h-6 w-6 text-slate-500" /></button>
        </div>
        <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Nombre(s) *" value={form.nombres} set={(value) => setForm({...form, nombres: value})} />
          <Field label="Apellido paterno" value={form.apellido_paterno} set={(value) => setForm({...form, apellido_paterno: value})} />
          <Field label="Apellido materno" value={form.apellido_materno} set={(value) => setForm({...form, apellido_materno: value})} />
          <Field label="Clave de arranque" value={form.clave_arranque} set={(value) => setForm({...form, clave_arranque: value})} />
          <Field label="Clave definitiva" value={form.clave_definitiva} set={(value) => setForm({...form, clave_definitiva: value})} />
          <Field label="Promotoría *" value={form.promotoria} set={(value) => setForm({...form, promotoria: value})} list="agent-promotorias" />
          <Field label="RFC" value={form.rfc} set={(value) => setForm({...form, rfc: value.toUpperCase()})} />
          <Field label="Inicio vigencia cédula" type="date" value={form.inicio_vigencia_cedula} set={(value) => setForm({...form, inicio_vigencia_cedula: value})} />
          <Field label="Fin vigencia cédula" type="date" value={form.fin_vigencia_cedula} set={(value) => setForm({...form, fin_vigencia_cedula: value})} />
          <Field label="Clasificación comercial" value={form.clasificacion_comercial} set={(value) => setForm({...form, clasificacion_comercial: value})} list="agent-classifications" />
          <Field label="Estatus Met" value={form.estatus_met} set={(value) => setForm({...form, estatus_met: value})} list="agent-statuses" />
          <datalist id="agent-promotorias">{directory.catalogs.promotorias.map((value) => <option value={value} key={value} />)}</datalist>
          <datalist id="agent-classifications">{directory.catalogs.clasificaciones.map((value) => <option value={value} key={value} />)}</datalist>
          <datalist id="agent-statuses">{directory.catalogs.estatus_met.map((value) => <option value={value} key={value} />)}</datalist>
        </div>
        {error && <p className="mx-5 mb-4 rounded-lg bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}
        <div className="sticky bottom-0 flex justify-end gap-3 border-t bg-slate-50 p-4">
          <button onClick={() => setModalOpen(false)} className="px-4 py-2 font-semibold text-slate-600">Cancelar</button>
          <button onClick={save} disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-50">{saving ? 'Guardando...' : 'Guardar'}</button>
        </div>
      </div>
    </div>}
  </div>;
}

function formatDate(value: string): string {
  if (!value) return '—';
  const [year, month, day] = value.split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}

function Status({ value }: { value: string }) {
  if (!value) return <>—</>;
  const active = isActiveStatus(value);
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'}`}>{value}</span>;
}

function isActiveStatus(value: string): boolean {
  return ['activo', 'activa', 'vigente'].includes(value.trim().toLocaleLowerCase('es'));
}

function Summary({ icon: Icon, label, value }: { icon: typeof UserRoundCog; label: string; value: number }) {
  return <div className="flex items-center gap-4 rounded-xl bg-white p-5 shadow"><div className="rounded-full bg-blue-100 p-3 text-blue-700"><Icon className="h-6 w-6" /></div><div><p className="text-sm text-slate-500">{label}</p><p className="text-2xl font-bold text-slate-900">{value}</p></div></div>;
}

function Field({ label, value, set, type = 'text', list }: { label: string; value: string; set: (value: string) => void; type?: string; list?: string }) {
  return <label className="block text-sm font-semibold text-slate-700">{label}<input type={type} value={value} list={list} onChange={(event) => set(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></label>;
}
