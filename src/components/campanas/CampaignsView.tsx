'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, Eye, Loader2, LockKeyhole, MailCheck, Plus, RefreshCw, Save, Send, Users } from 'lucide-react';

import {
  AudienceRow,
  Campaign,
  CampaignAudience,
  CampaignDeliveryReport,
  CampaignInput,
  CampaignPreview,
  createCampaign,
  getCampaignDeliveries,
  getCampaignAudience,
  getCampaignPreview,
  prepareCampaign,
  reconcileCampaignBounces,
  sendCampaignBatch,
  sendCampaignTest,
  updateCampaign,
} from '@/modules/campanas/service';

const DEFAULT_BODY = `Hola {{nombre_cliente}},

⚠️ ¿Tienes Protección Garantizada MédicaLife?

Recuerda que si sales de tu empresa o dejas de pertenecer a su póliza de Gastos Médicos Mayores, tienes 60 días naturales para avisarnos y realizar los cambios necesarios en tu Protección Garantizada.

📅 No dejes pasar el plazo.

Si estás en esta situación, escríbenos y te acompañamos con el proceso para ayudarte a mantener tu protección de Gastos Médicos Mayores.

Póliza de referencia: {{numero_poliza}}
Agente: {{agente}}

Saludos,
TAIICO Life Advisors`;

const EMPTY_CAMPAIGN: CampaignInput = {
  nombre: 'Recordatorio Protección Garantizada MédicaLife',
  asunto: '⚠️ Información importante sobre tu Protección Garantizada MédicaLife',
  cuerpo: DEFAULT_BODY,
  deducible_minimo: 1000000,
};

export function CampaignsView({ initialCampaigns, safeVariables }: { initialCampaigns: Campaign[]; safeVariables: string[] }) {
  const [campaigns, setCampaigns] = useState(initialCampaigns);
  const [selectedId, setSelectedId] = useState(initialCampaigns[0]?.id || '');
  const selected = campaigns.find((item) => item.id === selectedId) || null;
  const locked = Boolean(selected && selected.estatus !== 'borrador');
  const [draft, setDraft] = useState<CampaignInput>(selected ? campaignInput(selected) : EMPTY_CAMPAIGN);
  const [creating, setCreating] = useState(initialCampaigns.length === 0);
  const [audience, setAudience] = useState<CampaignAudience | null>(null);
  const [selectedRecipient, setSelectedRecipient] = useState('');
  const [preview, setPreview] = useState<CampaignPreview | null>(null);
  const [testEmail, setTestEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [loadingAudience, setLoadingAudience] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [showMissingOnly, setShowMissingOnly] = useState(false);
  const [deliveryReport, setDeliveryReport] = useState<CampaignDeliveryReport | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [preparing, setPreparing] = useState(false);
  const [sendingBatch, setSendingBatch] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const lastField = useRef<'asunto' | 'cuerpo'>('cuerpo');

  useEffect(() => {
    if (!selected) return;
    setDraft(campaignInput(selected));
    setCreating(false);
    setAudience(null); setPreview(null); setSelectedRecipient(''); setDeliveryReport(null); setConfirmation(''); setError(''); setMessage('');
    if (selected.estatus !== 'borrador') getCampaignDeliveries(selected.id).then(setDeliveryReport).catch(() => undefined);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !deliveryReport?.summary.enviando) return;
    const timer = window.setInterval(() => getCampaignDeliveries(selectedId).then(setDeliveryReport).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [selectedId, deliveryReport?.summary.enviando]);

  const displayedRows = useMemo(() => {
    const rows = audience?.rows || [];
    return showMissingOnly ? rows.filter((row) => !row.email) : rows;
  }, [audience, showMissingOnly]);

  async function save() {
    setSaving(true); setError(''); setMessage('');
    try {
      const saved = creating ? await createCampaign(draft) : await updateCampaign(selectedId, draft);
      setCampaigns((rows) => creating ? [saved, ...rows] : rows.map((row) => row.id === saved.id ? saved : row));
      setSelectedId(saved.id); setCreating(false); setMessage('Borrador guardado correctamente.');
      return saved;
    } catch (requestError) {
      setError(errorText(requestError)); return null;
    } finally { setSaving(false); }
  }

  async function loadAudience() {
    let campaign = selected;
    if (creating || !campaign || hasChanges(campaign, draft)) campaign = await save();
    if (!campaign) return;
    setLoadingAudience(true); setError('');
    try {
      const next = await getCampaignAudience(campaign.id);
      setAudience(next);
      const first = next.rows[0]?.key || '';
      setSelectedRecipient(first);
      setPreview(first ? await getCampaignPreview(campaign.id, first) : null);
    } catch (requestError) { setError(errorText(requestError)); }
    finally { setLoadingAudience(false); }
  }

  async function selectRecipient(row: AudienceRow) {
    if (!selectedId) return;
    setSelectedRecipient(row.key); setError('');
    try { setPreview(await getCampaignPreview(selectedId, row.key)); }
    catch (requestError) { setError(errorText(requestError)); }
  }

  async function sendTest() {
    if (!selectedId || !selectedRecipient) return;
    setSendingTest(true); setError(''); setMessage('');
    try {
      const result = await sendCampaignTest(selectedId, selectedRecipient, testEmail);
      setMessage(`Prueba enviada a ${result.recipient}.`);
    } catch (requestError) { setError(errorText(requestError)); }
    finally { setSendingTest(false); }
  }

  async function prepareDeliveries() {
    if (!selectedId) return;
    setPreparing(true); setError(''); setMessage('');
    try {
      const report = await prepareCampaign(selectedId);
      setDeliveryReport(report);
      setCampaigns((rows) => rows.map((row) => row.id === selectedId ? {...row, estatus:'preparada'} : row));
      setMessage('Audiencia congelada. Revisa las exclusiones antes de confirmar cualquier envío.');
    } catch (requestError) { setError(errorText(requestError)); }
    finally { setPreparing(false); }
  }

  async function sendBatch() {
    if (!selectedId) return;
    setSendingBatch(true); setError(''); setMessage('');
    try {
      const result = await sendCampaignBatch(selectedId, confirmation, 20);
      setMessage(`Lote de ${result.accepted} correos aceptado. Puedes seguir el avance en esta pantalla.`);
      setConfirmation('');
      setDeliveryReport(await getCampaignDeliveries(selectedId));
    } catch (requestError) { setError(errorText(requestError)); }
    finally { setSendingBatch(false); }
  }

  async function reconcileBounces() {
    if (!selectedId) return;
    setReconciling(true); setError(''); setMessage('');
    try {
      const report = await reconcileCampaignBounces(selectedId);
      setDeliveryReport(report);
      setMessage(`Conciliación terminada: ${report.matched} dirección(es) con rebote identificadas en ${report.scanned} mensajes revisados.`);
    } catch (requestError) { setError(errorText(requestError)); }
    finally { setReconciling(false); }
  }

  function exportReport() {
    if (!deliveryReport) return;
    const headings = ['Cliente','RFC','Póliza','Correo','Estatus','Intentos','Fecha de envío','Detalle'];
    const rows = deliveryReport.deliveries.map((item) => [item.nombre_cliente,item.rfc,item.numero_poliza,item.email,item.estatus,String(item.intentos),item.sent_at || '',item.error]);
    const csv = [headings, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href=url; link.download=`campana-${selected?.nombre || 'reporte'}.csv`; link.click(); URL.revokeObjectURL(url);
  }

  function insertVariable(variable: string) {
    const token = `{{${variable}}}`;
    setDraft((current) => ({ ...current, [lastField.current]: `${current[lastField.current]}${current[lastField.current].endsWith(' ') || current[lastField.current].endsWith('\n') ? '' : ' '}${token}` }));
  }

  function newCampaign() {
    setCreating(true); setSelectedId(''); setDraft(EMPTY_CAMPAIGN); setAudience(null); setPreview(null); setDeliveryReport(null); setConfirmation(''); setError(''); setMessage('');
  }

  return <div className="flex h-full min-h-0 flex-col overflow-y-auto p-4 sm:p-8">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div><h1 className="text-3xl font-bold text-white">Campañas</h1><p className="mt-1 text-blue-100">Segmenta clientes, redacta comunicaciones y valida cada mensaje antes de enviarlo.</p></div>
      <button type="button" onClick={newCampaign} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2.5 font-semibold text-blue-700 shadow"><Plus className="h-5 w-5" />Nueva campaña</button>
    </div>

    <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="rounded-xl bg-white p-4 shadow">
        <h2 className="mb-3 font-bold text-slate-900">Borradores</h2>
        <div className="space-y-2">
          {campaigns.map((campaign) => <button key={campaign.id} type="button" onClick={() => setSelectedId(campaign.id)} className={`w-full rounded-lg border p-3 text-left ${selectedId === campaign.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:bg-slate-50'}`}><span className="block font-semibold text-slate-900">{campaign.nombre}</span><span className="mt-1 block text-xs text-slate-500">{campaign.estatus} · {new Date(campaign.updated_at).toLocaleDateString('es-MX')}</span></button>)}
          {campaigns.length === 0 && <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">Todavía no hay campañas guardadas.</p>}
        </div>
      </aside>

      <section className="space-y-5">
        <div className="rounded-xl bg-white p-5 shadow sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold text-slate-900">{creating ? 'Nueva campaña' : selected?.estatus === 'borrador' ? 'Editar borrador' : 'Campaña preparada'}</h2><p className="text-sm text-slate-500">Revisa la audiencia, realiza una prueba interna y congela los mensajes antes del envío controlado.</p></div>{(creating || selected?.estatus === 'borrador') && <button type="button" onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Guardar borrador</button>}</div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <Field label="Nombre interno de la campaña" value={draft.nombre} set={(value) => setDraft({...draft,nombre:value})} disabled={locked} />
            <Field label="Deducible mínimo" type="number" value={String(draft.deducible_minimo)} set={(value) => setDraft({...draft,deducible_minimo:Number(value)})} prefix="$" disabled={locked} />
          </div>
          <label className="mt-4 block text-sm font-semibold text-slate-700">Asunto del correo<input value={draft.asunto} disabled={locked} onFocus={() => { lastField.current='asunto'; }} onChange={(event) => setDraft({...draft,asunto:event.target.value})} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 disabled:bg-slate-100" /></label>
          <label className="mt-4 block text-sm font-semibold text-slate-700">Cuerpo del correo<textarea value={draft.cuerpo} disabled={locked} onFocus={() => { lastField.current='cuerpo'; }} onChange={(event) => setDraft({...draft,cuerpo:event.target.value})} rows={12} className="mt-1.5 w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 font-mono text-sm font-normal text-slate-900 disabled:bg-slate-100" /></label>
          <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs font-semibold uppercase text-slate-500">Insertar variable:</span>{safeVariables.map((variable) => <button type="button" key={variable} disabled={locked} onClick={() => insertVariable(variable)} className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50">{`{{${variable}}}`}</button>)}</div>
          <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900"><strong>Segmento inicial:</strong> MetLife GMM, póliza vigente según FFINVIG y deducible igual o mayor a {currency(draft.deducible_minimo)}. Protección Garantizada se identifica por el deducible; no se trata como un producto distinto.</div>
          {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}{message && <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
          <button type="button" onClick={loadAudience} disabled={loadingAudience || saving} className="mt-5 inline-flex items-center gap-2 rounded-lg border border-blue-600 px-4 py-2.5 font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-50">{loadingAudience ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}Generar audiencia y vista previa</button>
        </div>

        {audience && <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="Pólizas" value={audience.summary.policies} /><Metric label="Clientes únicos" value={audience.summary.unique_clients} /><Metric label="Con correo" value={audience.summary.clients_with_email} good /><Metric label="Sin correo" value={audience.summary.clients_missing_email} warning /><Metric label="Varias pólizas" value={audience.summary.clients_with_multiple_policies} /></div>
          <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.35fr)_minmax(22rem,.65fr)]">
            <div className="min-w-0 rounded-xl bg-white shadow">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4"><div><h3 className="font-bold text-slate-900">Audiencia identificada</h3><p className="text-xs text-slate-500">Una fila por póliza; los clientes con varias pólizas están señalados.</p></div><label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={showMissingOnly} onChange={(event) => setShowMissingOnly(event.target.checked)} />Mostrar únicamente sin correo</label></div>
              <div className="max-h-[34rem] overflow-auto"><table className="min-w-[920px] w-full text-left text-sm"><thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Cliente / RFC','Póliza','Producto','Deducible','Fin vigencia','Agente','Correo'].map((heading) => <th key={heading} className="px-4 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y">{displayedRows.map((row) => <tr key={row.key} onClick={() => selectRecipient(row)} className={`cursor-pointer text-slate-700 hover:bg-blue-50 ${selectedRecipient === row.key ? 'bg-blue-50' : ''}`}><td className="px-4 py-3"><span className="font-semibold text-slate-900">{row.nombre_cliente}</span><span className="block text-xs text-slate-400">{row.rfc || 'RFC no registrado'}{row.multiple_policies ? ' · Varias pólizas' : ''}</span></td><td className="px-4 py-3">{row.numero_poliza}</td><td className="px-4 py-3">{row.nombre_producto}</td><td className="px-4 py-3 font-semibold">{currency(row.deducible)}</td><td className="px-4 py-3">{row.fecha_fin_vigencia}</td><td className="px-4 py-3">{row.agente || '—'}</td><td className="px-4 py-3">{row.email ? <span className="text-emerald-700">{row.email}</span> : <span className="inline-flex items-center gap-1 text-amber-700"><AlertTriangle className="h-4 w-4" />Faltante</span>}</td></tr>)}</tbody></table></div>
            </div>
            <div className="rounded-xl bg-white p-5 shadow">
              <div className="flex items-center gap-2"><Eye className="h-5 w-5 text-blue-600" /><h3 className="font-bold text-slate-900">Vista previa personalizada</h3></div>
              {preview ? <div className="mt-4"><p className="text-xs font-semibold uppercase text-slate-400">Ejemplo para</p><p className="font-semibold text-slate-900">{preview.recipient.nombre_cliente} · {preview.recipient.numero_poliza}</p><div className="mt-4 rounded-lg border border-slate-200"><div className="border-b bg-slate-50 p-3 text-sm"><strong>Asunto:</strong> {preview.subject}</div><div className="whitespace-pre-wrap p-4 text-sm leading-6 text-slate-700">{preview.body}</div></div>{preview.missing_variables.length > 0 ? <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800"><AlertTriangle className="mr-1 inline h-4 w-4" />Faltan: {preview.missing_variables.join(', ')}</p> : <p className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-emerald-700"><CheckCircle2 className="h-4 w-4" />Todas las variables se resolvieron.</p>}</div> : <p className="mt-4 text-sm text-slate-500">Selecciona una póliza para generar la vista previa.</p>}
              <div className="mt-6 border-t pt-5"><div className="flex items-center gap-2"><MailCheck className="h-5 w-5 text-blue-600" /><h4 className="font-bold text-slate-900">Enviar prueba interna</h4></div><p className="mt-1 text-xs text-slate-500">Solo se aceptan destinatarios @taiico.com. No se enviará al cliente.</p><input type="email" value={testEmail} onChange={(event) => setTestEmail(event.target.value)} placeholder="usuario@taiico.com" className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm" /><button type="button" onClick={sendTest} disabled={!testEmail || !selectedRecipient || sendingTest || Boolean(preview?.missing_variables.length)} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 font-semibold text-white disabled:opacity-50">{sendingTest ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Enviar prueba</button></div>
              {!deliveryReport && <div className="mt-5 border-t pt-5"><div className="flex items-center gap-2"><LockKeyhole className="h-5 w-5 text-amber-600" /><h4 className="font-bold text-slate-900">Congelar audiencia</h4></div><p className="mt-1 text-xs text-slate-500">Crea una copia exacta de destinatarios y mensajes. Después de este paso el contenido ya no podrá editarse.</p><button type="button" onClick={prepareDeliveries} disabled={preparing || !audience} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 font-semibold text-white disabled:opacity-50">{preparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}Preparar envíos</button></div>}
            </div>
          </div>
        </>}

        {deliveryReport && <div className="rounded-xl bg-white p-5 shadow sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><Send className="h-5 w-5 text-blue-600" /><h3 className="text-lg font-bold text-slate-900">Control de envíos</h3></div><div className="flex flex-wrap gap-2"><button type="button" onClick={exportReport} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"><Download className="h-4 w-4" />Exportar CSV</button><button type="button" onClick={reconcileBounces} disabled={reconciling || deliveryReport.summary.enviados === 0} className="inline-flex items-center gap-2 rounded-lg border border-blue-600 px-3 py-2 text-sm font-semibold text-blue-700 disabled:opacity-50">{reconciling ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Conciliar rebotes</button></div></div>
          <p className="mt-1 text-sm text-slate-500">Los mensajes están congelados. Cada lote contiene como máximo 20 correos y nunca se reintenta automáticamente.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><Metric label="Pendientes" value={deliveryReport.summary.pendientes} /><Metric label="Enviando" value={deliveryReport.summary.enviando} /><Metric label="Enviados" value={deliveryReport.summary.enviados} good /><Metric label="Rebotados" value={deliveryReport.summary.rebotados} warning /><Metric label="Sin correo" value={deliveryReport.summary.sin_correo} warning /><Metric label="Otras incidencias" value={deliveryReport.summary.rechazados + deliveryReport.summary.errores + deliveryReport.summary.entrega_incierta + deliveryReport.summary.variables_incompletas} warning /></div>
          {deliveryReport.summary.pendientes > 0 && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4"><p className="font-semibold text-red-900">Confirmación requerida</p><p className="mt-1 text-sm text-red-700">Para enviar el siguiente lote escribe exactamente: <strong>{selected?.nombre}</strong></p><input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-3 w-full rounded-lg border border-red-200 bg-white px-3 py-2.5 text-sm" /><button type="button" onClick={sendBatch} disabled={sendingBatch || confirmation !== selected?.nombre} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 font-semibold text-white disabled:opacity-50">{sendingBatch ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Enviar siguiente lote de hasta 20</button></div>}
          <div className="mt-5 max-h-[28rem] overflow-auto rounded-lg border"><table className="min-w-[850px] w-full text-left text-sm"><thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Cliente / RFC','Póliza','Correo','Estatus','Intentos','Detalle'].map((heading) => <th key={heading} className="px-4 py-3">{heading}</th>)}</tr></thead><tbody className="divide-y">{deliveryReport.deliveries.map((item) => <tr key={item.id} className="text-slate-700"><td className="px-4 py-3"><strong className="text-slate-900">{item.nombre_cliente}</strong><span className="block text-xs text-slate-400">{item.rfc || 'RFC no registrado'}</span></td><td className="px-4 py-3">{item.numero_poliza}</td><td className="px-4 py-3">{item.email || '—'}</td><td className="px-4 py-3"><DeliveryStatus status={item.estatus} /></td><td className="px-4 py-3">{item.intentos}</td><td className="max-w-sm px-4 py-3 text-xs text-slate-500">{item.error || (item.sent_at ? `Enviado ${new Date(item.sent_at).toLocaleString('es-MX')}` : '—')}</td></tr>)}</tbody></table></div>
          <p className="mt-3 text-xs text-slate-500">“Enviado” significa que Gmail aceptó el mensaje. Los rebotes posteriores se conciliarán en una etapa posterior.</p>
        </div>}
      </section>
    </div>
  </div>;
}

function campaignInput(campaign: Campaign): CampaignInput { return { nombre: campaign.nombre, asunto: campaign.asunto, cuerpo: campaign.cuerpo, deducible_minimo: campaign.deducible_minimo }; }
function hasChanges(campaign: Campaign, draft: CampaignInput) { const current=campaignInput(campaign); return Object.keys(current).some((key) => current[key as keyof CampaignInput] !== draft[key as keyof CampaignInput]); }
function errorText(error: unknown) { return error instanceof Error ? error.message.replace('API Error: ', '') : 'Ocurrió un error inesperado.'; }
function currency(value: number) { return new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN',maximumFractionDigits:0}).format(value || 0); }
function Field({label,value,set,type='text',prefix,disabled=false}: {label:string;value:string;set:(value:string)=>void;type?:string;prefix?:string;disabled?:boolean}) { return <label className="block text-sm font-semibold text-slate-700">{label}<div className="relative mt-1.5">{prefix && <span className="absolute left-3 top-2.5 text-slate-400">{prefix}</span>}<input type={type} value={value} disabled={disabled} min={type==='number'?0:undefined} onChange={(event)=>set(event.target.value)} className={`w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 disabled:bg-slate-100 ${prefix?'pl-7':''}`} /></div></label>; }
function Metric({label,value,good,warning}: {label:string;value:number;good?:boolean;warning?:boolean}) { return <div className="rounded-xl bg-white p-4 shadow"><p className="text-xs font-semibold uppercase text-slate-500">{label}</p><p className={`mt-1 text-2xl font-bold ${good?'text-emerald-700':warning?'text-amber-700':'text-slate-900'}`}>{value}</p></div>; }
function DeliveryStatus({status}: {status:string}) { const tone=status==='enviado'?'bg-emerald-100 text-emerald-800':status==='pendiente'?'bg-blue-100 text-blue-800':status==='enviando'?'bg-indigo-100 text-indigo-800':status==='sin_correo'||status==='variables_incompletas'?'bg-amber-100 text-amber-800':'bg-red-100 text-red-800'; return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{status}</span>; }
function csvCell(value:string) { return `"${String(value || '').replaceAll('"','""')}"`; }
