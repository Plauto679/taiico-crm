'use client';

import { useMemo, useState } from 'react';
import { CalendarDays, ExternalLink, Pencil, Plus, UsersRound, X } from 'lucide-react';
import { Collaborator, CollaboratorInput, Vacation, createCollaborator, createVacation, updateCollaborator } from '@/modules/rrhh/service';

const emptyPerson: CollaboratorInput = { nombre_completo: '', inicio_colaboracion: new Date().toISOString().slice(0, 10), expediente: '', puesto: '', area: '', tipo_relacion: 'Empleado', estatus: 'Activo', dias_vacaciones_anuales: 12, notas: '' };

export function RRHHView({ initialCollaborators, initialVacations, sourceUrl }: { initialCollaborators: Collaborator[]; initialVacations: Vacation[]; sourceUrl: string }) {
  const [people, setPeople] = useState(initialCollaborators);
  const [vacations, setVacations] = useState(initialVacations);
  const [tab, setTab] = useState<'personas' | 'vacaciones'>('personas');
  const [personModal, setPersonModal] = useState(false);
  const [vacationModal, setVacationModal] = useState(false);
  const [editing, setEditing] = useState<Collaborator | null>(null);
  const [person, setPerson] = useState<CollaboratorInput>(emptyPerson);
  const [vacation, setVacation] = useState({ collaborator_id: '', fecha_inicio: '', fecha_fin: '', estatus: 'Solicitada', comentarios: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const active = people.filter((item) => item.estatus.toLocaleLowerCase('es') === 'activo').length;
  const upcoming = useMemo(() => vacations.filter((item) => item.fecha_inicio >= new Date().toISOString().slice(0, 10) && item.estatus.toLocaleLowerCase('es') !== 'rechazada').length, [vacations]);
  const used = people.reduce((sum, item) => sum + item.dias_vacaciones_usados, 0);

  function openPerson(item?: Collaborator) {
    setEditing(item || null);
    setPerson(item ? { nombre_completo: item.nombre_completo, inicio_colaboracion: item.inicio_colaboracion, expediente: item.expediente, puesto: item.puesto, area: item.area, tipo_relacion: item.tipo_relacion, estatus: item.estatus, dias_vacaciones_anuales: item.dias_vacaciones_anuales, notas: item.notas } : emptyPerson);
    setError(''); setPersonModal(true);
  }

  async function savePerson() {
    setSaving(true); setError('');
    try {
      const saved = editing ? await updateCollaborator(editing.id, person) : await createCollaborator(person);
      setPeople((rows) => editing ? rows.map((row) => row.id === editing.id ? saved : row) : [...rows, saved]);
      setPersonModal(false);
    } catch (e) { setError(e instanceof Error ? e.message.replace('API Error: ', '') : 'No se pudo guardar'); }
    finally { setSaving(false); }
  }

  async function saveVacation() {
    setSaving(true); setError('');
    try { const saved = await createVacation(vacation); setVacations((rows) => [...rows, saved]); setVacationModal(false); }
    catch (e) { setError(e instanceof Error ? e.message.replace('API Error: ', '') : 'No se pudo guardar'); }
    finally { setSaving(false); }
  }

  return <div className="flex h-full min-h-0 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
    <div className="flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-3xl font-bold text-white">RRHH</h1><p className="mt-1 text-blue-100">Colaboradores, antigüedad, expedientes y vacaciones.</p></div><a href={sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-white/40 px-4 py-2 font-semibold text-white hover:bg-white/10"><ExternalLink className="h-4 w-4" />Abrir fuente en Drive</a></div>
    <div className="grid gap-4 sm:grid-cols-3"><Summary icon={UsersRound} label="Colaboradores activos" value={active} /><Summary icon={CalendarDays} label="Próximas vacaciones" value={upcoming} /><Summary icon={CalendarDays} label="Días usados este año" value={used} /></div>
    <div className="flex flex-col gap-2 border-b border-white/30 sm:flex-row sm:items-center sm:justify-between"><div className="flex overflow-x-auto"><button onClick={() => setTab('personas')} className={`shrink-0 px-5 py-3 font-semibold ${tab === 'personas' ? 'border-b-2 border-white text-white' : 'text-blue-100'}`}>Colaboradores</button><button onClick={() => setTab('vacaciones')} className={`shrink-0 px-5 py-3 font-semibold ${tab === 'vacaciones' ? 'border-b-2 border-white text-white' : 'text-blue-100'}`}>Vacaciones</button></div><button onClick={() => tab === 'personas' ? openPerson() : (setError(''), setVacationModal(true))} className="mb-2 inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-2 font-semibold text-blue-700"><Plus className="h-4 w-4" />{tab === 'personas' ? 'Agregar colaborador' : 'Registrar vacaciones'}</button></div>
    <div className="overflow-x-auto rounded-xl bg-white shadow">
      {tab === 'personas' ? <table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Nombre', 'Inicio', 'Antigüedad', 'Puesto / Área', 'Relación', 'Vacaciones', 'Estatus', 'Expediente', ''].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody className="divide-y">{people.map((item) => <tr key={item.id} className="text-slate-700"><td className="px-4 py-3 font-semibold text-slate-900">{item.nombre_completo}</td><td className="px-4 py-3">{item.inicio_colaboracion}</td><td className="px-4 py-3">{item.dias_colaborando} días</td><td className="px-4 py-3">{item.puesto || '—'}<span className="block text-xs text-slate-400">{item.area}</span></td><td className="px-4 py-3">{item.tipo_relacion}</td><td className="px-4 py-3"><span className="font-semibold">{item.dias_vacaciones_disponibles}</span> disponibles<span className="block text-xs text-slate-400">{item.dias_vacaciones_usados} usados</span></td><td className="px-4 py-3">{item.estatus}</td><td className="px-4 py-3">{item.expediente ? <a href={item.expediente} onClick={(e) => e.stopPropagation()} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">Abrir</a> : '—'}</td><td className="px-4 py-3"><button onClick={() => openPerson(item)} className="rounded-lg border p-2 text-slate-500 hover:text-blue-700"><Pencil className="h-4 w-4" /></button></td></tr>)}</tbody></table> : <table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Colaborador', 'Inicio', 'Fin', 'Días', 'Estatus', 'Comentarios'].map((h) => <th key={h} className="px-4 py-3">{h}</th>)}</tr></thead><tbody className="divide-y">{vacations.map((item) => <tr key={item.id} className="text-slate-700"><td className="px-4 py-3 font-semibold">{item.nombre_completo}</td><td className="px-4 py-3">{item.fecha_inicio}</td><td className="px-4 py-3">{item.fecha_fin}</td><td className="px-4 py-3">{item.dias}</td><td className="px-4 py-3">{item.estatus}</td><td className="px-4 py-3">{item.comentarios || '—'}</td></tr>)}</tbody></table>}
    </div>
    {personModal && <Modal title={editing ? 'Editar colaborador' : 'Nuevo colaborador'} close={() => setPersonModal(false)} save={savePerson} saving={saving} error={error}><div className="grid gap-4 sm:grid-cols-2"><Field label="Nombre completo" value={person.nombre_completo} set={(v) => setPerson({...person, nombre_completo:v})} /><Field label="Inicio de colaboración" type="date" value={person.inicio_colaboracion} set={(v) => setPerson({...person, inicio_colaboracion:v})} /><Field label="Puesto" value={person.puesto} set={(v) => setPerson({...person, puesto:v})} /><Field label="Área" value={person.area} set={(v) => setPerson({...person, area:v})} /><Select label="Tipo de relación" value={person.tipo_relacion} options={['Empleado','Honorarios','Prácticas','Otro']} set={(v) => setPerson({...person,tipo_relacion:v})} /><Select label="Estatus" value={person.estatus} options={['Activo','Inactivo','Baja','Licencia']} set={(v) => setPerson({...person,estatus:v})} /><Field label="Días de vacaciones anuales" type="number" value={String(person.dias_vacaciones_anuales)} set={(v) => setPerson({...person,dias_vacaciones_anuales:Number(v)})} /><Field label="Expediente (URL)" value={person.expediente} set={(v) => setPerson({...person,expediente:v})} /></div><Field label="Notas" value={person.notas} set={(v) => setPerson({...person,notas:v})} /></Modal>}
    {vacationModal && <Modal title="Registrar vacaciones" close={() => setVacationModal(false)} save={saveVacation} saving={saving} error={error}><Select label="Colaborador" value={vacation.collaborator_id} options={people.filter(p => p.estatus === 'Activo').map(p => `${p.id}|${p.nombre_completo}`)} displayPipe set={(v) => setVacation({...vacation,collaborator_id:v})} /><div className="grid gap-4 sm:grid-cols-2"><Field label="Fecha inicio" type="date" value={vacation.fecha_inicio} set={(v) => setVacation({...vacation,fecha_inicio:v})} /><Field label="Fecha fin" type="date" value={vacation.fecha_fin} set={(v) => setVacation({...vacation,fecha_fin:v})} /></div><Select label="Estatus" value={vacation.estatus} options={['Solicitada','Aprobada','Rechazada','Tomada']} set={(v) => setVacation({...vacation,estatus:v})} /><Field label="Comentarios" value={vacation.comentarios} set={(v) => setVacation({...vacation,comentarios:v})} /></Modal>}
  </div>;
}

function Summary({ icon: Icon, label, value }: { icon: typeof UsersRound; label: string; value: number }) { return <div className="flex items-center gap-4 rounded-xl bg-white p-5 shadow"><div className="rounded-full bg-blue-100 p-3 text-blue-700"><Icon className="h-6 w-6" /></div><div><p className="text-sm text-slate-500">{label}</p><p className="text-2xl font-bold text-slate-900">{value}</p></div></div>; }
function Field({ label, value, set, type='text' }: { label:string; value:string; set:(v:string)=>void; type?:string }) { return <label className="block text-sm font-semibold text-slate-700">{label}<input type={type} value={value} onChange={e=>set(e.target.value)} className="mt-1.5 w-full rounded-lg border px-3 py-2.5 font-normal text-slate-900" /></label>; }
function Select({ label, value, options, set, displayPipe=false }: { label:string; value:string; options:string[]; set:(v:string)=>void; displayPipe?:boolean }) { return <label className="block text-sm font-semibold text-slate-700">{label}<select value={value} onChange={e=>set(displayPipe ? e.target.value.split('|')[0] : e.target.value)} className="mt-1.5 w-full rounded-lg border bg-white px-3 py-2.5 font-normal text-slate-900"><option value="">Selecciona una opción</option>{options.map(o => { const [id,name]=o.split('|'); return <option key={o} value={displayPipe?id:o}>{displayPipe?name:o}</option>; })}</select></label>; }
function Modal({ title, close, save, saving, error, children }: { title:string; close:()=>void; save:()=>void; saving:boolean; error:string; children:React.ReactNode }) { return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4"><div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl"><div className="flex justify-between border-b p-5"><h2 className="text-xl font-bold text-slate-900">{title}</h2><button onClick={close}><X className="h-5 w-5 text-slate-500" /></button></div><div className="space-y-4 p-6">{children}{error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}</div><div className="flex justify-end gap-3 border-t bg-slate-50 p-4"><button onClick={close} className="px-4 py-2 font-semibold text-slate-600">Cancelar</button><button onClick={save} disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white disabled:opacity-50">{saving?'Guardando...':'Guardar'}</button></div></div></div>; }
