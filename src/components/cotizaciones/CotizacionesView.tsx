'use client';

import { useEffect, useMemo, useState } from 'react';
import { Bot, CheckCircle2, Clipboard, ExternalLink, FileText, Link2, Loader2, Mail, MessageSquareText, Plus, Save, Search, Send, Upload, UserRoundPlus, X } from 'lucide-react';
import {
  answerQuoteBrowserSession,
  createQuote,
  createQuoteDataRequestLink,
  getQuoteEmailDraft,
  openQuoteBrowserSession,
  releaseQuoteBrowserSession,
  searchQuoteClients,
  sendQuoteEmail,
  startQuote,
  updateQuote,
  uploadQuoteDocument,
  type Quote,
  type QuoteAgent,
  type QuoteBrowserSession,
  type QuoteClient,
  type QuoteDocumentFile,
} from '@/modules/cotizaciones/service';

type Props = {
  initialQuotes: Quote[];
  products: Record<string, string[]>;
  insurer: string;
  agents: QuoteAgent[];
  agentIsAutomatic: boolean;
  quotationPortalCredentialsConfigured: boolean;
};

export function CotizacionesView({ initialQuotes, products, insurer, agents, agentIsAutomatic, quotationPortalCredentialsConfigured }: Props) {
  const [quotes, setQuotes] = useState(initialQuotes);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [clients, setClients] = useState<QuoteClient[]>([]);
  const [selected, setSelected] = useState<QuoteClient | null>(null);
  const [prospect, setProspect] = useState(false);
  const [prospectName, setProspectName] = useState('');
  const [ramo, setRamo] = useState('GMM');
  const [producto, setProducto] = useState(products.GMM?.[0] || '');
  const [agentRfc, setAgentRfc] = useState(agentIsAutomatic ? (agents[0]?.rfc || '') : '');
  const [agentPromotoria, setAgentPromotoria] = useState(agentIsAutomatic ? (agents[0]?.promotoria || '') : '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Quote | null>(null);
  const [editAgentRfc, setEditAgentRfc] = useState('');
  const [editAgentPromotoria, setEditAgentPromotoria] = useState('');
  const [editCliente, setEditCliente] = useState('');
  const [editRfc, setEditRfc] = useState('');
  const [editRamo, setEditRamo] = useState('GMM');
  const [editProducto, setEditProducto] = useState('');
  const [editError, setEditError] = useState('');
  const [starting, setStarting] = useState<Quote | null>(null);
  const [startRfc, setStartRfc] = useState('');
  const [startError, setStartError] = useState('');
  const [conversationQuote, setConversationQuote] = useState<Quote | null>(null);
  const [browserSession, setBrowserSession] = useState<QuoteBrowserSession | null>(null);
  const [browserStarting, setBrowserStarting] = useState(false);
  const [browserError, setBrowserError] = useState('');
  const [selectedBrowserAnswer, setSelectedBrowserAnswer] = useState<string | null>(null);
  const [answerSubmitting, setAnswerSubmitting] = useState(false);
  const [uploadingDocument, setUploadingDocument] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState('');
  const [sendingQuote, setSendingQuote] = useState<Quote | null>(null);
  const [quoteFiles, setQuoteFiles] = useState<QuoteDocumentFile[]>([]);
  const [selectedQuoteFileIds, setSelectedQuoteFileIds] = useState<string[]>([]);
  const [quoteEmailStep, setQuoteEmailStep] = useState<'files' | 'email'>('files');
  const [quoteEmailRecipients, setQuoteEmailRecipients] = useState('');
  const [quoteEmailSubject, setQuoteEmailSubject] = useState('');
  const [quoteEmailBody, setQuoteEmailBody] = useState('');
  const [quoteEmailFolderLink, setQuoteEmailFolderLink] = useState('');
  const [quoteEmailLoading, setQuoteEmailLoading] = useState(false);
  const [quoteEmailSending, setQuoteEmailSending] = useState(false);
  const [quoteEmailError, setQuoteEmailError] = useState('');
  const [quoteEmailSuccess, setQuoteEmailSuccess] = useState('');
  const [requestingDataQuote, setRequestingDataQuote] = useState<Quote | null>(null);
  const [dataRequestLink, setDataRequestLink] = useState('');
  const [dataRequestExpiresAt, setDataRequestExpiresAt] = useState('');
  const [dataRequestLoading, setDataRequestLoading] = useState(false);
  const [dataRequestError, setDataRequestError] = useState('');
  const [dataRequestCopied, setDataRequestCopied] = useState(false);

  useEffect(() => {
    if (!open || selected || prospect || query.trim().length < 2) {
      setClients([]);
      return;
    }
    const timer = window.setTimeout(() => {
      searchQuoteClients(query).then(setClients).catch(() => setClients([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [open, query, selected, prospect]);

  const availableProducts = useMemo(() => products[ramo] || [], [products, ramo]);

  function reset() {
    setQuery('');
    setClients([]);
    setSelected(null);
    setProspect(false);
    setProspectName('');
    setRamo('GMM');
    setProducto(products.GMM?.[0] || '');
    setAgentRfc(agentIsAutomatic ? (agents[0]?.rfc || '') : '');
    setAgentPromotoria(agentIsAutomatic ? (agents[0]?.promotoria || '') : '');
    setError('');
  }

  async function submit() {
    setSaving(true);
    setError('');
    try {
      const quote = await createQuote({
        client_id: selected?.id,
        prospect_name: prospect ? prospectName : undefined,
        ramo,
        producto,
        agent_rfc: agentRfc || undefined,
        agent_promotoria: agentPromotoria || undefined,
      });
      setQuotes((current) => [...current, quote]);
      setOpen(false);
      reset();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo registrar');
    } finally {
      setSaving(false);
    }
  }

  function openEdit(quote: Quote) {
    const matchedAgent = agents.find((agent) => agent.promotoria === quote.promotoria && agent.key === quote.clave_agente);
    setEditing(quote);
    setEditAgentRfc(agentIsAutomatic ? (agents[0]?.rfc || '') : (matchedAgent?.rfc || ''));
    setEditAgentPromotoria(agentIsAutomatic ? (agents[0]?.promotoria || '') : (matchedAgent?.promotoria || ''));
    setEditCliente(quote.cliente);
    setEditRfc(quote.rfc);
    setEditRamo(quote.ramo);
    setEditProducto(quote.producto);
    setEditError('');
  }

  async function saveEdit() {
    if (!editing) return;
    setSaving(true);
    setEditError('');
    try {
      const updated = await updateQuote(editing.id, {
        cliente: editCliente,
        rfc: editRfc || undefined,
        ramo: editRamo,
        producto: editProducto,
        agent_rfc: editAgentRfc || undefined,
        agent_promotoria: editAgentPromotoria || undefined,
      });
      setQuotes((current) => current.map((quote) => quote.id === editing.id ? updated : quote));
      setEditing(null);
    } catch (exception) {
      setEditError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo actualizar');
    } finally {
      setSaving(false);
    }
  }

  function openStart(quote: Quote) {
    setStarting(quote);
    setStartRfc(quote.rfc || '');
    setStartError('');
  }

  async function beginQuotation() {
    if (!starting) return;
    setSaving(true);
    setStartError('');
    try {
      const updated = await startQuote(starting.id, startRfc);
      setQuotes((current) => current.map((quote) => quote.id === starting.id ? updated : quote));
      setStarting(null);
      setConversationQuote(updated);
      setBrowserSession(null);
      setBrowserError('');
      setSelectedBrowserAnswer(null);
      setAnswerSubmitting(false);
    } catch (exception) {
      setStartError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo iniciar la cotización');
    } finally {
      setSaving(false);
    }
  }

  async function openAgentBrowser() {
    if (!conversationQuote) return;
    setBrowserStarting(true);
    setBrowserError('');
    setSelectedBrowserAnswer(null);
    setAnswerSubmitting(false);
    try {
      const session = await openQuoteBrowserSession(conversationQuote.id);
      setBrowserSession(session);
      if (session.status === 'busy' || session.status === 'failed') {
      setBrowserError(session.error_message || 'No se pudo abrir la sesión de navegador');
      }
    } catch (exception) {
      setBrowserError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo abrir la sesión de navegador');
    } finally {
      setBrowserStarting(false);
    }
  }

  async function submitBrowserAnswer(questionId: string, optionId: string, label: string, value?: string | null) {
    if (!conversationQuote) return;
    setAnswerSubmitting(true);
    setBrowserError('');
    setSelectedBrowserAnswer(label);
    try {
      const session = await answerQuoteBrowserSession(conversationQuote.id, {
        question_id: questionId,
        option_id: optionId,
        value: value || label,
      });
      setBrowserSession(session);
      if (session.status === 'busy' || session.status === 'failed') {
        setBrowserError(session.error_message || 'No se pudo continuar la sesión de navegador');
      }
    } catch (exception) {
      setBrowserError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo continuar la sesión de navegador');
    } finally {
      setAnswerSubmitting(false);
    }
  }

  async function releaseAndRetryAgentBrowser() {
    if (!conversationQuote) return;
    setBrowserStarting(true);
    setBrowserError('');
    setSelectedBrowserAnswer(null);
    setAnswerSubmitting(false);
    try {
      await releaseQuoteBrowserSession(conversationQuote.id);
      setBrowserSession(null);
      const session = await openQuoteBrowserSession(conversationQuote.id);
      setBrowserSession(session);
      if (session.status === 'busy' || session.status === 'failed') {
        setBrowserError(session.error_message || 'No se pudo abrir la sesión de navegador');
      }
    } catch (exception) {
      setBrowserError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo reiniciar la sesión de navegador');
    } finally {
      setBrowserStarting(false);
    }
  }

  function openConversation(quote: Quote) {
    setConversationQuote(quote);
    setBrowserSession(null);
    setBrowserError('');
    setSelectedBrowserAnswer(null);
    setAnswerSubmitting(false);
  }

  function closeConversation() {
    if (conversationQuote && browserSession && browserSession.status !== 'failed' && browserSession.status !== 'busy') {
      releaseQuoteBrowserSession(conversationQuote.id).catch(() => undefined);
    }
    setConversationQuote(null);
    setBrowserSession(null);
    setBrowserError('');
    setSelectedBrowserAnswer(null);
    setAnswerSubmitting(false);
  }

  async function uploadDocumentForQuote(
    quote: Quote,
    documentKind: 'cotizaciones' | 'documentos_adicionales',
    file?: File,
  ) {
    if (!file) return;
    const uploadKey = `${quote.id}:${documentKind}`;
    setUploadingDocument(uploadKey);
    setUploadError('');
    try {
      const updated = await uploadQuoteDocument(quote.id, documentKind, file);
      setQuotes((current) => current.map((item) => item.id === quote.id ? updated : item));
      if (conversationQuote?.id === quote.id) {
        setConversationQuote(updated);
      }
    } catch (exception) {
      setUploadError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo cargar el archivo');
    } finally {
      setUploadingDocument(null);
    }
  }

  async function openSendQuote(quote: Quote) {
    setSendingQuote(quote);
    setQuoteFiles([]);
    setSelectedQuoteFileIds([]);
    setQuoteEmailStep('files');
    setQuoteEmailRecipients('');
    setQuoteEmailSubject('');
    setQuoteEmailBody('');
    setQuoteEmailFolderLink('');
    setQuoteEmailError('');
    setQuoteEmailSuccess('');
    setQuoteEmailLoading(true);
    try {
      const draft = await getQuoteEmailDraft(quote.id);
      setQuoteFiles(draft.files);
      setSelectedQuoteFileIds(draft.files.map((file) => file.id));
      setQuoteEmailRecipients(draft.default_recipients.join(', '));
      setQuoteEmailSubject(draft.default_subject);
      setQuoteEmailBody(draft.default_body);
      setQuoteEmailFolderLink(draft.folder_link);
    } catch (exception) {
      setQuoteEmailError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudieron leer los archivos de cotización');
    } finally {
      setQuoteEmailLoading(false);
    }
  }

  function closeSendQuote() {
    setSendingQuote(null);
    setQuoteFiles([]);
    setSelectedQuoteFileIds([]);
    setQuoteEmailError('');
    setQuoteEmailSuccess('');
  }

  function toggleQuoteFile(fileId: string) {
    setSelectedQuoteFileIds((current) => (
      current.includes(fileId)
        ? current.filter((id) => id !== fileId)
        : [...current, fileId]
    ));
  }

  async function submitQuoteEmail() {
    if (!sendingQuote) return;
    const recipients = quoteEmailRecipients
      .split(/[,\n;]/)
      .map((item) => item.trim())
      .filter(Boolean);
    setQuoteEmailSending(true);
    setQuoteEmailError('');
    setQuoteEmailSuccess('');
    try {
      const result = await sendQuoteEmail(sendingQuote.id, {
        file_ids: selectedQuoteFileIds,
        recipients,
        subject: quoteEmailSubject,
        body: quoteEmailBody,
      });
      setQuoteEmailSuccess(`Cotización enviada a ${result.recipients.join(', ')} con ${result.attachment_count} archivo(s).`);
    } catch (exception) {
      setQuoteEmailError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo enviar la cotización');
    } finally {
      setQuoteEmailSending(false);
    }
  }

  async function openDataRequest(quote: Quote) {
    setRequestingDataQuote(quote);
    setDataRequestLink('');
    setDataRequestExpiresAt('');
    setDataRequestError('');
    setDataRequestCopied(false);
    setDataRequestLoading(true);
    try {
      const result = await createQuoteDataRequestLink(quote.id);
      const publicLink = `${window.location.origin}${result.path}`;
      setDataRequestLink(publicLink);
      setDataRequestExpiresAt(result.expires_at);
    } catch (exception) {
      setDataRequestError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo crear la liga');
    } finally {
      setDataRequestLoading(false);
    }
  }

  function closeDataRequest() {
    setRequestingDataQuote(null);
    setDataRequestLink('');
    setDataRequestError('');
    setDataRequestCopied(false);
  }

  async function copyDataRequestLink() {
    if (!dataRequestLink) return;
    await navigator.clipboard.writeText(dataRequestLink);
    setDataRequestCopied(true);
    window.setTimeout(() => setDataRequestCopied(false), 1800);
  }

  function renderFolderActions(
    quote: Quote,
    documentKind: 'cotizaciones' | 'documentos_adicionales',
    folderLink: string,
    emptyLabel: string,
  ) {
    const inputId = `${documentKind}-${quote.id}`;
    const uploadKey = `${quote.id}:${documentKind}`;
    const uploading = uploadingDocument === uploadKey;
    return (
      <div className="flex min-w-36 flex-col gap-2" onClick={(event) => event.stopPropagation()}>
        <input
          id={inputId}
          type="file"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            uploadDocumentForQuote(quote, documentKind, file);
          }}
        />
        <label
          htmlFor={inputId}
          className={`inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold ${uploading ? 'border-slate-200 bg-slate-100 text-slate-400' : 'border-blue-200 bg-blue-50 text-blue-700 hover:border-blue-300 hover:bg-blue-100'}`}
        >
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? 'Cargando...' : 'Cargar archivo'}
        </label>
        {folderLink ? (
          <a className="inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-blue-700" href={folderLink} target="_blank" rel="noreferrer">
            Ver carpeta <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : (
          <span className="text-xs text-slate-400">{emptyLabel}</span>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col items-stretch justify-between gap-3 rounded-xl bg-white p-4 shadow-sm sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Control de cotizaciones</h2>
          <p className="text-sm text-slate-500">Registros sincronizados con Cotizaciones.xlsx</p>
        </div>
        <button onClick={() => setOpen(true)} className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white shadow hover:bg-blue-700">
          <Plus className="h-5 w-5" /> Cotizar
        </button>
      </div>

      <div className="overflow-hidden rounded-xl bg-white shadow-sm">
        {uploadError && <div className="border-b border-red-100 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{uploadError}</div>}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>{['Folio', 'Agente', 'Promotoría', 'Aseguradora', 'Clave', 'Cliente / Prospecto', 'RFC', 'Ramo', 'Producto', 'Estatus', 'Cotizaciones', 'Documentos adicionales', 'Acciones'].map((header) => <th key={header} className="px-4 py-3">{header}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {quotes.map((quote) => (
                <tr key={quote.id} onClick={() => openEdit(quote)} className="cursor-pointer hover:bg-blue-50/40">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{quote.id}</td>
                  <td className="px-4 py-3">{quote.agente}</td>
                  <td className="whitespace-nowrap px-4 py-3">{quote.promotoria}</td>
                  <td className="px-4 py-3">{quote.aseguradora}</td>
                  <td className="whitespace-nowrap px-4 py-3">{quote.clave_agente}</td>
                  <td className="px-4 py-3">{quote.cliente}</td>
                  <td className="whitespace-nowrap px-4 py-3">{quote.rfc || 'Prospecto'}</td>
                  <td className="px-4 py-3">{quote.ramo}</td>
                  <td className="px-4 py-3">{quote.producto}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{quote.estatus}</span></td>
                  <td className="px-4 py-3">{renderFolderActions(quote, 'cotizaciones', quote.cotizaciones, quote.rfc ? 'Se creará al cargar' : 'RFC requerido')}</td>
                  <td className="px-4 py-3">{renderFolderActions(quote, 'documentos_adicionales', quote.documentos_adicionales, quote.rfc ? 'Se creará al cargar' : 'RFC requerido')}</td>
                  <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                    <div className="flex min-w-40 flex-col gap-2">
                      {quote.estatus === 'Lista para cotizar' ? (
                        <button onClick={() => openConversation(quote)} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 font-semibold text-white hover:bg-blue-700"><MessageSquareText className="h-4 w-4" /> Iniciar cotización</button>
                      ) : (
                        <button onClick={() => openStart(quote)} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 font-semibold text-white hover:bg-blue-700"><Bot className="h-4 w-4" /> Iniciar cotización</button>
                      )}
                      <button onClick={() => openSendQuote(quote)} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-100"><Mail className="h-4 w-4" /> Enviar cotización</button>
                      <button onClick={() => openDataRequest(quote)} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 font-semibold text-indigo-700 hover:border-indigo-300 hover:bg-indigo-100"><Clipboard className="h-4 w-4" /> Solicitar datos</button>
                    </div>
                  </td>
                </tr>
              ))}
              {!quotes.length && <tr><td colSpan={13} className="px-6 py-16 text-center text-slate-500"><FileText className="mx-auto mb-3 h-9 w-9 text-slate-300" />Aún no hay cotizaciones registradas.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div><h2 className="text-xl font-bold text-slate-900">Nueva cotización</h2><p className="mt-1 text-sm text-slate-500">Primero identifica al cliente; después elige ramo y producto.</p></div>
              <button onClick={() => { setOpen(false); reset(); }} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-6 p-6">
              <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="space-y-2 text-sm font-semibold text-slate-700">
                    Agente
                    {agentIsAutomatic ? (
                      <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 font-normal text-slate-900">
                        {agents[0] ? `${agents[0].name} · ${agents[0].rfc}` : 'No se encontró el agente asociado a tu RFC'}
                      </div>
                    ) : (
                      <select value={agentRfc && agentPromotoria ? `${agentRfc}|${agentPromotoria}` : ''} onChange={(event) => { const [rfc, promotoria] = event.target.value.split('|'); setAgentRfc(rfc || ''); setAgentPromotoria(promotoria || ''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900">
                        <option value="">Selecciona un agente</option>
                        {agents.map((agent) => <option key={`${agent.rfc}-${agent.promotoria}`} value={`${agent.rfc}|${agent.promotoria}`}>{agent.name} · {agent.rfc} · {agent.promotoria}</option>)}
                      </select>
                    )}
                  </label>
                  <div className="space-y-2 text-sm font-semibold text-slate-700">
                    Asignación automática
                    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 font-normal text-slate-700">
                      {(() => {
                        const agent = agents.find((item) => item.rfc === agentRfc && item.promotoria === agentPromotoria);
                        return agent ? `${agent.promotoria} · ${insurer} · Clave ${agent.key}` : `${insurer} · Promotoría y clave pendientes`;
                      })()}
                    </div>
                  </div>
                </div>
              </section>
              {!selected && !prospect ? (
                <section className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Buscar cliente por nombre o RFC</label>
                  <div className="relative"><Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ej. AAMA950203I52 o Alberto Alfaro" className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></div>
                  {!!clients.length && <div className="max-h-52 divide-y overflow-y-auto rounded-lg border">{clients.map((client) => <button key={client.id} onClick={() => setSelected(client)} className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-blue-50"><span className="font-medium text-slate-800">{client.nombre}</span><span className="text-sm text-slate-500">{client.rfc || 'Sin RFC'}</span></button>)}</div>}
                  {query.trim().length >= 2 && !clients.length && <p className="text-sm text-slate-500">No encontramos coincidencias. Puedes registrar la cotización como prospecto.</p>}
                  <button onClick={() => { setProspect(true); setProspectName(query.trim()); }} className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-800"><UserRoundPlus className="h-4 w-4" /> No existe: crear prospecto</button>
                </section>
              ) : (
                <section className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">{selected ? 'Cliente existente' : 'Prospecto nuevo'}</p>
                  {prospect ? <input value={prospectName} onChange={(event) => setProspectName(event.target.value)} placeholder="Nombre completo del prospecto" className="mt-2 w-full rounded-lg border border-blue-200 bg-white px-3 py-2.5 text-slate-900" /> : <><p className="mt-1 font-semibold text-slate-900">{selected?.nombre}</p><p className="text-sm text-slate-600">RFC: {selected?.rfc}</p></>}
                  <button onClick={() => { setSelected(null); setProspect(false); }} className="mt-2 text-xs font-semibold text-blue-700 hover:underline">Cambiar cliente</button>
                </section>
              )}

              {(selected || prospect) && <div className="grid gap-5 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-semibold text-slate-700">Ramo<select value={ramo} onChange={(event) => { const next = event.target.value; setRamo(next); setProducto(products[next]?.[0] || ''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900"><option>GMM</option><option>Vida</option></select></label>
                <label className="space-y-2 text-sm font-semibold text-slate-700">Producto<select value={producto} onChange={(event) => setProducto(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900">{availableProducts.map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>}
              {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4"><button onClick={() => { setOpen(false); reset(); }} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Cancelar</button><button disabled={saving || !agentRfc || (!selected && !prospect) || (prospect && prospectName.trim().length < 2)} onClick={submit} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{saving && <Loader2 className="h-4 w-4 animate-spin" />} Registrar cotización</button></div>
          </div>
        </div>
      )}

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div><h2 className="text-xl font-bold text-slate-900">Editar cotización</h2><p className="mt-1 text-sm text-slate-500">El RFC puede permanecer vacío hasta solicitar la cotización real.</p></div>
              <button onClick={() => setEditing(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-5 p-6">
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-semibold text-slate-700">Cliente / Prospecto<input value={editCliente} onChange={(event) => setEditCliente(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
                <label className="space-y-2 text-sm font-semibold text-slate-700">RFC <span className="font-normal text-slate-400">(opcional)</span><input value={editRfc} onChange={(event) => setEditRfc(event.target.value.toUpperCase())} placeholder="Se solicitará antes de cotizar" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal uppercase text-slate-900" /></label>
              </div>
              <label className="block space-y-2 text-sm font-semibold text-slate-700">Agente
                {agentIsAutomatic ? <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 font-normal text-slate-900">{agents[0] ? `${agents[0].name} · ${agents[0].rfc}` : 'No se encontró el agente asociado a tu RFC'}</div> : <select value={editAgentRfc && editAgentPromotoria ? `${editAgentRfc}|${editAgentPromotoria}` : ''} onChange={(event) => { const [rfc, promotoria] = event.target.value.split('|'); setEditAgentRfc(rfc || ''); setEditAgentPromotoria(promotoria || ''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900"><option value="">Selecciona un agente</option>{agents.map((agent) => <option key={`${agent.rfc}-${agent.promotoria}`} value={`${agent.rfc}|${agent.promotoria}`}>{agent.name} · {agent.rfc} · {agent.promotoria}</option>)}</select>}
              </label>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-semibold text-slate-700">Ramo<select value={editRamo} onChange={(event) => { const next = event.target.value; setEditRamo(next); setEditProducto(products[next]?.[0] || ''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900"><option>GMM</option><option>Vida</option></select></label>
                <label className="space-y-2 text-sm font-semibold text-slate-700">Producto<select value={editProducto} onChange={(event) => setEditProducto(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900">{(products[editRamo] || []).map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>
              <div className="grid gap-4 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-3"><div><span className="block text-xs font-semibold uppercase text-slate-400">Aseguradora</span>{insurer}</div><div><span className="block text-xs font-semibold uppercase text-slate-400">Estatus</span>{editing.estatus}</div><div><span className="block text-xs font-semibold uppercase text-slate-400">RFC requerido</span>Al solicitar cotización</div></div>
              {editError && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{editError}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4"><button onClick={() => setEditing(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Cancelar</button><button disabled={saving || editCliente.trim().length < 2 || !editAgentRfc} onClick={saveEdit} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar cambios</button></div>
          </div>
        </div>
      )}

      {starting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Iniciar cotización</h2>
                <p className="mt-1 text-sm text-slate-500">Se preparará la carpeta del cliente en Drive antes de entrar al portal de MetLife.</p>
              </div>
              <button onClick={() => setStarting(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-5 p-6">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="font-semibold text-slate-900">{starting.cliente}</p>
                <p>{starting.ramo} · {starting.producto} · {starting.agente}</p>
              </div>
              <label className="block space-y-2 text-sm font-semibold text-slate-700">
                RFC del cliente
                <input autoFocus value={startRfc} onChange={(event) => setStartRfc(event.target.value.toUpperCase())} placeholder="Ej. VEHL941016933" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal uppercase text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
              </label>
              <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
                El flujo flexible de MetLife debe leer opciones del portal en tiempo real. Esta preparación deja el registro listo y con carpeta para guardar el PDF cuando termine la cotización.
              </div>
              {!quotationPortalCredentialsConfigured && (
                <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
                  Faltan las credenciales específicas de cotización del portal de MetLife. Configura `METLIFE_QUOTATION_PORTAL_USERNAME` y `METLIFE_QUOTATION_PORTAL_PASSWORD` antes de ejecutar el navegador automático.
                </div>
              )}
              {startError && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{startError}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4">
              <button onClick={() => setStarting(null)} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Cancelar</button>
              <button disabled={saving || startRfc.trim().length < 12} onClick={beginQuotation} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />} Preparar cotización</button>
            </div>
          </div>
        </div>
      )}

      {sendingQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Enviar cotización</h2>
                <p className="mt-1 text-sm text-slate-500">Selecciona los archivos de cotización y confirma el correo antes de enviarlo.</p>
              </div>
              <button onClick={closeSendQuote} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-5 p-6">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="font-semibold text-slate-900">{sendingQuote.cliente}</p>
                <p>{sendingQuote.ramo} · {sendingQuote.producto} · {sendingQuote.rfc || 'Sin RFC'}</p>
              </div>

              {quoteEmailStep === 'files' ? (
                <section className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-slate-900">Archivos disponibles en Cotizaciones</h3>
                    {quoteEmailFolderLink && (
                      <a href={quoteEmailFolderLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:underline">
                        Ver carpeta <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                  </div>
                  {quoteEmailLoading ? (
                    <div className="flex items-center gap-2 rounded-xl border border-slate-200 p-4 text-sm text-slate-600">
                      <Loader2 className="h-4 w-4 animate-spin" /> Leyendo archivos de Drive…
                    </div>
                  ) : quoteFiles.length ? (
                    <div className="divide-y overflow-hidden rounded-xl border border-slate-200">
                      {quoteFiles.map((file) => (
                        <label key={file.id} className="flex cursor-pointer items-start gap-3 px-4 py-3 hover:bg-blue-50">
                          <input
                            type="checkbox"
                            checked={selectedQuoteFileIds.includes(file.id)}
                            onChange={() => toggleQuoteFile(file.id)}
                            className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-semibold text-slate-800">{file.name}</span>
                            <span className="block text-xs text-slate-500">{file.modifiedTime ? `Modificado: ${new Date(file.modifiedTime).toLocaleString('es-MX')}` : 'Archivo en Drive'}</span>
                          </span>
                          {file.webViewLink && (
                            <a onClick={(event) => event.stopPropagation()} href={file.webViewLink} target="_blank" rel="noreferrer" className="text-blue-700 hover:text-blue-900">
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          )}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                      No encontré archivos en la carpeta de cotizaciones de este registro. Carga al menos una cotización antes de enviarla.
                    </div>
                  )}
                </section>
              ) : (
                <section className="space-y-4">
                  <label className="block space-y-2 text-sm font-semibold text-slate-700">
                    Destinatarios
                    <input
                      value={quoteEmailRecipients}
                      onChange={(event) => setQuoteEmailRecipients(event.target.value)}
                      placeholder="cliente@correo.com, otro@correo.com"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                    <span className="block text-xs font-normal text-slate-400">Puedes separar varios correos con coma, punto y coma o salto de línea.</span>
                  </label>
                  <label className="block space-y-2 text-sm font-semibold text-slate-700">
                    Asunto
                    <input
                      value={quoteEmailSubject}
                      onChange={(event) => setQuoteEmailSubject(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                  </label>
                  <label className="block space-y-2 text-sm font-semibold text-slate-700">
                    Cuerpo del correo
                    <textarea
                      value={quoteEmailBody}
                      onChange={(event) => setQuoteEmailBody(event.target.value)}
                      rows={9}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                  </label>
                  <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
                    Se adjuntarán {selectedQuoteFileIds.length} archivo(s): {quoteFiles.filter((file) => selectedQuoteFileIds.includes(file.id)).map((file) => file.name).join(', ')}
                  </div>
                </section>
              )}

              {quoteEmailError && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{quoteEmailError}</p>}
              {quoteEmailSuccess && <p className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{quoteEmailSuccess}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4">
              <button onClick={quoteEmailStep === 'email' ? () => setQuoteEmailStep('files') : closeSendQuote} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">
                {quoteEmailStep === 'email' ? 'Atrás' : 'Cancelar'}
              </button>
              {quoteEmailStep === 'files' ? (
                <button disabled={quoteEmailLoading || selectedQuoteFileIds.length === 0} onClick={() => setQuoteEmailStep('email')} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                  Continuar
                </button>
              ) : (
                <button disabled={quoteEmailSending || !quoteEmailRecipients.trim() || !quoteEmailSubject.trim() || !quoteEmailBody.trim() || selectedQuoteFileIds.length === 0} onClick={submitQuoteEmail} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                  {quoteEmailSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Enviar cotización
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {conversationQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div>
                <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900">
                  <MessageSquareText className="h-5 w-5 text-blue-600" />
                  Conversación de cotización
                </h2>
                <p className="mt-1 text-sm text-slate-500">La carpeta del cliente ya está preparada. Aquí iniciaremos el flujo flexible con el portal de MetLife.</p>
              </div>
              <button onClick={closeConversation} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid min-h-0 flex-1 gap-0 overflow-y-auto lg:grid-cols-[1fr_280px]">
              <section className="space-y-4 p-6">
                <div className="rounded-2xl bg-blue-50 p-4 text-sm text-blue-950">
                  <p className="font-semibold">Agente cotizador</p>
                  <p className="mt-1">Estoy por comenzar la cotización {conversationQuote.id} para {conversationQuote.cliente}. El navegador automático trabajará en una sesión controlada; tú solo deberías interactuar desde esta conversación.</p>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-700">
                  <p className="font-semibold text-slate-900">Contexto cargado</p>
                  <ul className="mt-3 space-y-2">
                    <li><span className="font-semibold">RFC:</span> {conversationQuote.rfc}</li>
                    <li><span className="font-semibold">Ramo:</span> {conversationQuote.ramo}</li>
                    <li><span className="font-semibold">Producto:</span> {conversationQuote.producto}</li>
                    <li><span className="font-semibold">Agente:</span> {conversationQuote.agente}</li>
                    <li><span className="font-semibold">Estatus:</span> {conversationQuote.estatus}</li>
                  </ul>
                </div>
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
                  El ejecutor usa una sesión persistente de Chrome por MFA. Por seguridad, solo se permite una cotización activa por sesión de MetLife para evitar cruces de estado entre pestañas.
                </div>
                {browserSession && (
                  <div className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-700">
                    <p className="font-semibold text-slate-900">Sesión de navegador</p>
                    <p className="mt-1">Estado: <span className="font-semibold">{browserSession.status}</span></p>
                    {browserSession.current_url && <p className="mt-1 break-all text-xs text-slate-500">{browserSession.current_url}</p>}
                    <ol className="mt-3 space-y-1">
                      {browserSession.steps.map((step) => (
                        <li key={`${step.step_name}-${step.started_at}`} className="flex items-start justify-between gap-3">
                          <span>{step.step_name}</span>
                          <span className={step.status === 'completed' ? 'text-emerald-700' : step.status === 'failed' ? 'text-red-700' : 'text-slate-500'}>{step.status}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
                {browserSession?.prompt && (
                  <div className="rounded-2xl bg-blue-50 p-4 text-sm text-blue-950">
                    <p className="font-semibold">Agente cotizador</p>
                    <p className="mt-2 leading-6">{browserSession.prompt}</p>
                    {browserSession.question && (
                      <div className="mt-4 space-y-3">
                        <p className="font-semibold">{browserSession.question.text}</p>
                        <div className="grid gap-2">
                          {browserSession.question.options.map((option) => (
                            <button
                              key={option.id}
                              type="button"
                              disabled={answerSubmitting}
                              onClick={() => submitBrowserAnswer(browserSession.question!.id, option.id, option.label, option.value)}
                              className="rounded-xl border border-blue-200 bg-white px-4 py-3 text-left text-sm text-blue-950 shadow-sm hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50"
                            >
                              <span className="block font-semibold">{option.label}</span>
                              {option.description && <span className="mt-1 block text-xs text-blue-700">{option.description}</span>}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {selectedBrowserAnswer && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                    <p><span className="font-semibold">Respuesta registrada:</span> {selectedBrowserAnswer}</p>
                    <p className="mt-1">{answerSubmitting ? 'Aplicando respuesta en el portal de MetLife…' : 'Respuesta enviada al ejecutor de navegador.'}</p>
                  </div>
                )}
                {browserError && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{browserError}</p>}
              </section>
              <aside className="space-y-3 border-t bg-slate-50 p-6 lg:border-l lg:border-t-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Acciones</p>
                {conversationQuote.cotizaciones && (
                  <a href={conversationQuote.cotizaciones} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-50">
                    Abrir carpeta Drive <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                <button disabled={browserStarting} onClick={openAgentBrowser} className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                  {browserStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                  Iniciar agente
                </button>
                {browserSession?.status === 'busy' && (
                  <button disabled={browserStarting} onClick={releaseAndRetryAgentBrowser} className="w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50">
                    Liberar sesión y reintentar
                  </button>
                )}
                <button onClick={closeConversation} className="w-full rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Volver a cotizaciones</button>
              </aside>
            </div>
          </div>
        </div>
      )}

      {requestingDataQuote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div>
                <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900">
                  <Clipboard className="h-5 w-5 text-indigo-600" />
                  Solicitar datos
                </h2>
                <p className="mt-1 text-sm text-slate-500">Genera una liga temporal de 24 horas para que el prospecto complete sus datos de emisión.</p>
              </div>
              <button onClick={closeDataRequest} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-5 p-6">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="font-semibold text-slate-900">{requestingDataQuote.cliente}</p>
                <p className="mt-1">RFC: {requestingDataQuote.rfc}</p>
                <p>Producto: {requestingDataQuote.producto}</p>
              </div>

              {dataRequestLoading ? (
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 text-sm text-slate-600">
                  <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
                  Creando liga temporal…
                </div>
              ) : dataRequestLink ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                    <p className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4" /> Liga creada</p>
                    {dataRequestExpiresAt && <p className="mt-1">Expira: {new Date(dataRequestExpiresAt).toLocaleString('es-MX')}</p>}
                  </div>
                  <label className="block space-y-2 text-sm font-semibold text-slate-700">
                    Liga para enviar al prospecto
                    <input readOnly value={dataRequestLink} className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 font-normal text-slate-900" />
                  </label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button onClick={copyDataRequestLink} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
                      <Link2 className="h-4 w-4" />
                      {dataRequestCopied ? 'Liga copiada' : 'Copiar liga'}
                    </button>
                    <a href={dataRequestLink} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                      Abrir liga <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
                    Cuando el prospecto envíe el formulario, sus respuestas se guardarán como JSON y los documentos caerán en la carpeta <span className="font-semibold">Solicitud de datos-{requestingDataQuote.producto}-fecha</span>. También se notificará al agente y a alberto.alfaro@taiico.com.
                  </div>
                </div>
              ) : null}

              {dataRequestError && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{dataRequestError}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4">
              <button onClick={closeDataRequest} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Cerrar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
