'use client';

import { useState } from 'react';
import { ArrowDown, ArrowUp, Check, Pencil, Plus, X, ArchiveRestore, BarChart3, Briefcase, CakeSlice, Calendar, ChartNoAxesCombined, ClipboardList, ContactRound, DatabaseZap, DollarSign, FilePenLine, HandCoins, Landmark, Mail, MailCheck, Megaphone, PartyPopper, ScrollText, UserCog, UserRoundCog, UserRoundSearch, Users } from 'lucide-react';
import { SmartLink } from '@/components/navigation/SmartLink';
import { fetchFromApi } from '@/lib/api';

const WIDGETS = [
  ['cobranza', 'Cobranza', '/cobranza', 'Gestión de pagos y comisiones', DollarSign],
  ['renovaciones', 'Renovaciones', '/renovaciones', 'Próximos vencimientos y agenda', Calendar],
  ['cumpleanos', 'Cumpleaños de clientes', '/cumpleanos', 'Clientes, pólizas y agentes', CakeSlice],
  ['cumpleanos_agentes', 'Cumpleaños de agentes', '/cumpleanos-agentes', 'Agentes, claves y promotorías', PartyPopper],
  ['agentes', 'Agentes', '/agentes', 'Claves, cédulas y estatus MetLife', UserRoundCog],
  ['pendientes', 'Pendientes', '/pendientes', 'Emisión, servicios y siniestros', ClipboardList],
  ['cartera', 'Cartera de Prospectadores', '/cartera', 'Asignación por póliza', Briefcase],
  ['prospectadores', 'Prospectadores', '/prospectadores', 'Catálogo, pagos y cartera', UserRoundSearch],
  ['cobranza_prospectadores', 'Cobranza para prospectadores', '/cobranza-prospectadores', 'Comisiones y distribución mensual', HandCoins],
  ['clientes', 'Clientes', '/clientes', 'Directorio de contactos', Users],
  ['recluta', 'Recluta', '/recluta', 'Seguimiento de prospectos a agentes', UserRoundSearch],
  ['dashboards', 'Dashboards', '/dashboards', 'Datos y métricas', BarChart3],
  ['configuracion_mail', 'Configuración de Mail', '/configuracion-mail', 'Cuenta remitente y conexión SMTP', Mail],
  ['mails_automaticos', 'Mails automáticos', '/mails-automaticos', 'Programación y destinatarios', MailCheck],
  ['carga_bases', 'Carga de bases', '/carga-bases', 'Actualización controlada de pólizas', DatabaseZap],
  ['time_machine', 'Time Machine', '/time-machine', 'Consulta y restaura respaldos', ArchiveRestore],
  ['accesos', 'Accesos', '/accesos', 'Usuarios, roles y permisos', UserCog],
  ['cotizaciones', 'Cotizaciones', '/cotizaciones', 'Prospectos, productos y seguimiento', FilePenLine],
  ['gestion_comercial', 'Gestión Comercial', '/gestion-comercial', 'Oportunidades y seguimiento', ChartNoAxesCombined],
  ['logs', 'Logs', '/logs', 'Auditoría de usuarios y cambios', ScrollText],
  ['rrhh', 'RRHH', '/rrhh', 'Colaboradores, contratos y vacaciones', ContactRound],
  ['campanas', 'Campañas', '/campanas', 'Audiencias, mensajes y resultados', Megaphone],
  ['finanzas', 'Finanzas', '/finanzas', 'Movimientos, presupuestos y proyecciones', Landmark],
] as const;

export type HomeWidgetPreference = { allowed: string[]; selected: string[]; customized: boolean };

export function HomeWidgets({ initial }: { initial: HomeWidgetPreference }) {
  const [selected, setSelected] = useState(initial.selected);
  const [draft, setDraft] = useState(initial.selected);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const allowed = new Set(initial.allowed);
  const catalog = WIDGETS.filter(([key]) => allowed.has(key));
  const visible = selected.map((key) => catalog.find(([candidate]) => candidate === key)).filter((item) => item !== undefined);

  function toggle(key: string) {
    setDraft((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  function move(key: string, direction: -1 | 1) {
    setDraft((current) => {
      const next = [...current];
      const position = next.indexOf(key);
      const destination = position + direction;
      if (position < 0 || destination < 0 || destination >= next.length) return current;
      [next[position], next[destination]] = [next[destination], next[position]];
      return next;
    });
  }

  async function save() {
    setSaving(true); setError(''); setNotice('');
    try {
      const result = await fetchFromApi<HomeWidgetPreference>('/home-widgets', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module_keys: draft }),
      });
      setSelected(result.selected);
      setDraft(result.selected);
      setEditing(false);
      setNotice('Tu Inicio quedó personalizado.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudieron guardar las tarjetas.');
    } finally { setSaving(false); }
  }

  return <div className="w-full max-w-6xl space-y-5">
    <div className="flex justify-end"><button type="button" onClick={() => { setDraft(selected); setEditing(true); setError(''); setNotice(''); }} className="inline-flex items-center gap-2 rounded-lg border border-white/60 bg-white/10 px-4 py-2.5 font-semibold text-white hover:bg-white/20"><Pencil className="h-4 w-4" />Personalizar Inicio</button></div>
    {notice && <p role="status" className="rounded-lg bg-emerald-50 px-4 py-3 font-medium text-emerald-800">{notice}</p>}
    {visible.length ? <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-8 lg:grid-cols-4">{visible.map(([key, label, href, description, Icon]) => <SmartLink key={key} href={href} className="group block rounded-xl border border-transparent bg-white p-8 shadow-lg transition-all duration-300 hover:scale-105 hover:border-blue-400 hover:shadow-2xl"><div className="flex flex-col items-center space-y-4 text-center"><div className="rounded-full bg-blue-100 p-4 text-blue-700"><Icon className="h-8 w-8" /></div><div><h2 className="text-2xl font-bold text-gray-900">{label}</h2><p className="mt-2 text-gray-500">{description}</p></div></div></SmartLink>)}</div> : <div className="rounded-xl bg-white p-8 text-center text-slate-700">No tienes tarjetas en Inicio. Usa “Personalizar Inicio” para agregar las que necesites.</div>}
    {editing && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/65 p-4"><div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white text-slate-900 shadow-2xl"><div className="sticky top-0 flex items-start justify-between border-b bg-white p-5"><div><h2 className="text-xl font-bold">Personalizar Inicio</h2><p className="mt-1 text-sm text-slate-600">Elige y ordena tus tarjetas. Solo aparecen módulos autorizados.</p></div><button type="button" onClick={() => setEditing(false)} aria-label="Cerrar" className="rounded-full p-2 text-slate-600 hover:bg-slate-100"><X /></button></div><div className="space-y-2 p-5">{catalog.map(([key, label, , description, Icon]) => {
      const active = draft.includes(key);
      const position = draft.indexOf(key);
      return <div key={key} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3"><div className="rounded-full bg-blue-100 p-2 text-blue-700"><Icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="font-semibold">{label}</p><p className="text-xs text-slate-500">{description}</p></div>{active && <div className="flex gap-1"><button type="button" onClick={() => move(key, -1)} disabled={position === 0} aria-label={`Subir ${label}`} className="rounded p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30"><ArrowUp className="h-4 w-4" /></button><button type="button" onClick={() => move(key, 1)} disabled={position === draft.length - 1} aria-label={`Bajar ${label}`} className="rounded p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30"><ArrowDown className="h-4 w-4" /></button></div>}<button type="button" onClick={() => toggle(key)} aria-label={`${active ? 'Quitar' : 'Agregar'} ${label}`} className={`inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold ${active ? 'bg-slate-100 text-slate-700 hover:bg-slate-200' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'}`}>{active ? <><Check className="h-4 w-4" />Agregado</> : <><Plus className="h-4 w-4" />Agregar</>}</button></div>;
    })}</div>{error && <p role="alert" className="mx-5 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<div className="sticky bottom-0 flex justify-end gap-2 border-t bg-white p-5"><button type="button" onClick={() => setEditing(false)} className="rounded-lg border border-slate-300 px-4 py-2.5 font-semibold text-slate-700">Cancelar</button><button type="button" onClick={save} disabled={saving} className="rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white hover:bg-blue-800 disabled:opacity-50">{saving ? 'Guardando…' : 'Guardar cambios'}</button></div></div></div>}
  </div>;
}
