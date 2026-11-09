'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { fetchFromApi } from '@/lib/api';

type Data = { client_name: string; rfc: string; product: string; recognition: boolean; notes: string; paternal_surname: string; maternal_surname: string; maternal_surname_not_applicable: boolean; given_names: string; curp: string; email: string; phone: string };
type Agent = { rfc: string; name: string; promotoria: string };
type Config = { can_operate: boolean; can_review: boolean; agents: Agent[]; reasons: string[]; chat_ready: boolean; uploads_ready: boolean; ocr_ready: boolean; official_form: { can_generate: boolean; notice: string; version: string; source_url: string } };
type Document = { id: string; name: string; kind: string; at: string };
type Event = { action: string; actor: string; at: string; revision: number; status: string; comment?: string; reason?: string; target?: string };
type FormProgress = { supported: boolean; filled_count: number; mapped_count: number; pending_fields: { key: string; label: string; question: string; page: number; required_for_draft: boolean }[]; next_question: string; next_field: string | null; ready_for_partial_draft: boolean; manual_sections: { id: string; title: string; pages: string; question: string }[] };
type Proposal = { data: Data; revision: number; case_id: string; source_document?: string; evidence?: { field: string; value: string; page: number; method: string }[] };
type Case = { id: string; agent_rfc: string; promotoria: string; status: string; revision: number; data: Data; documents: Document[]; history: Event[]; requirements: string[]; missing: string[]; form_progress: FormProgress };
const empty: Data = { client_name: '', rfc: '', product: '', recognition: false, notes: '', paternal_surname: '', maternal_surname: '', maternal_surname_not_applicable: false, given_names: '', curp: '', email: '', phone: '' };
const states: Record<string, string> = { draft: 'En preparación', submitted: 'En espera de revisión', reviewing: 'En revisión', correction: 'Requiere corrección', validated: 'Validado por mesa' };
const actions: Record<string, string> = { created: 'Expediente creado', edited: 'Datos actualizados', document_uploaded: 'Documento aportado', submit: 'Enviado a revisión', claim: 'Revisión iniciada', correct: 'Corrección solicitada', validate: 'Validado por mesa', extraction_confirmed: 'Dato extraído confirmado', form_generated: 'Borrador oficial generado' };
const reasons: Record<string, string> = { documento_faltante: 'Documento faltante', ilegible: 'Documento ilegible', vigencia: 'Vigencia', datos_inconsistentes: 'Datos inconsistentes', captura: 'Error de captura', firma: 'Firma', otro: 'Otro' };
const identityFields = { paternal_surname: 'Apellido paterno', maternal_surname: 'Apellido materno', given_names: 'Nombre(s)', curp: 'CURP', email: 'Correo electrónico', phone: 'Teléfono' } as const;
type Extraction = { document_id: string; document_name: string; revision: number; notice: string; used_ocr: boolean; pages: { page: number; text: string; method: string; partial: boolean }[]; candidates: { field: string; value: string; page: number; excerpt: string; method: string }[] };
const field = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 disabled:bg-slate-100';
const button = 'rounded-xl bg-[#234b69] px-4 py-2.5 font-semibold text-white disabled:opacity-40';

function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    return fetchFromApi<T>('/mesa-control' + path, { method, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
}

export function MesaControlView() {
    const [config, setConfig] = useState<Config | null>(null);
    const [cases, setCases] = useState<Case[]>([]);
    const [partial, setPartial] = useState(false);
    const [selected, setSelected] = useState<Case | null>(null);
    const [data, setData] = useState<Data>(empty);
    const [agent, setAgent] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [busy, setBusy] = useState(false);
    const busyRef = useRef(false);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const requestId = useRef('');
    const [kind, setKind] = useState('');
    const [question, setQuestion] = useState('');
    const [answer, setAnswer] = useState('');
    const [extraction, setExtraction] = useState<Extraction | null>(null);
    const [proposal, setProposal] = useState<Proposal | null>(null);
    const [guideDocument, setGuideDocument] = useState<{ id: string; name: string; page_start: number } | null>(null);
    const [reason, setReason] = useState('documento_faltante');
    const [target, setTarget] = useState('');
    const [comment, setComment] = useState('');
    const [creating, setCreating] = useState(false);
    const fileInput = useRef<HTMLInputElement>(null);

    useEffect(() => {
        let active = true;
        Promise.all([api<Config>('/config'), api<{ cases: Case[]; partial: boolean }>('/cases')]).then(([cfg, list]) => {
            if (!active) return;
            setConfig(cfg); setCases(list.cases); setPartial(list.partial);
            if (cfg.agents.length === 1) setAgent(cfg.agents[0].rfc);
        }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, []);

    function choose(item: Case | null) {
        setSelected(item); setData({ ...empty, ...item?.data }); setExtraction(null); setGuideDocument(null); setCreating(!item);
        setKind(item?.requirements[0] || ''); setProposal(null); setAnswer(''); setQuestion(''); setComment(''); setTarget(''); setNotice(''); setError('');
        if (!item) requestId.current = crypto.randomUUID();
    }
    function save(item: Case) {
        setSelected(item); setData({ ...empty, ...item.data }); setExtraction(null); setGuideDocument(null); setCreating(false); setProposal(null);
        setKind(current => item.requirements.includes(current) ? current : item.requirements[0]);
        setCases(current => [item, ...current.filter(c => c.id !== item.id)]);
    }
    async function run(work: () => Promise<void>) {
        if (busyRef.current) return;
        busyRef.current = true; setBusy(true); setError(''); setNotice('');
        try { await work(); } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo completar la operación.'); }
        finally { busyRef.current = false; setBusy(false); }
    }
    function submitData(event: FormEvent) {
        event.preventDefault();
        void run(async () => {
            if (selected) save(await api<Case>(`/cases/${selected.id}`, 'PATCH', { revision: selected.revision, data }));
            else {
                const assigned = config?.agents.find(a => a.rfc === agent);
                if (!assigned) throw new Error('Selecciona el agente responsable.');
                if (!requestId.current) requestId.current = crypto.randomUUID();
                save(await api<Case>('/cases', 'POST', { request_id: requestId.current, agent_rfc: agent, promotoria: assigned.promotoria, data }));
            }
            setNotice('Expediente guardado. Continúa con los documentos.');
        });
    }
    function transition(action: string) {
        if (!selected) return;
        void run(async () => {
            save(await api<Case>(`/cases/${selected.id}/transition`, 'POST', { revision: selected.revision, action, reason, target, comment }));
            setComment(''); setTarget(''); setNotice('Estado actualizado y registrado en el historial.');
        });
    }
    const dirty = !!selected && JSON.stringify(data) !== JSON.stringify({ ...empty, ...selected.data });
    const editable = !!config?.can_operate && !busy;
    const visible = cases.filter(c => filter === 'all' || c.status === filter);
    return <div className="h-full overflow-y-auto bg-[#f3f5f6] text-slate-900">
        <header className="border-b border-slate-200 bg-white px-5 py-5 sm:px-10">
            <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
                <div><Link href="/" className="text-xs font-semibold tracking-widest text-slate-500">TAIICO</Link><h1 className="text-2xl font-semibold">Mesa de control</h1><p className="mt-1 text-sm text-slate-600">Prepara tu solicitud con Plauto y sigue su revisión.</p></div>
                <div className="flex items-center gap-3"><Link href="/pendientes" className="text-sm underline">Ver Pendientes</Link><button className={button} disabled={!editable} onClick={() => choose(null)}>Nueva solicitud</button></div>
            </div>
        </header>
        <div className="mx-auto max-w-6xl space-y-5 px-5 py-6 sm:px-10">
            {loading && <p role="status">Cargando tus expedientes…</p>}
            {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}{selected && <button className="ml-3 underline" disabled={busy} onClick={() => void run(async () => { choose(await api<Case>(`/cases/${selected.id}`)); })}>Recargar expediente</button>}</div>}
            {notice && <p role="status" className="rounded-xl bg-emerald-50 p-4 text-emerald-800">{notice}</p>}
            {!selected && !creating && config && <section className="flex items-center gap-5 rounded-2xl bg-white p-6 shadow-sm"><Image src="/plauto/plauto.png" alt="Plauto" width={70} height={82} /><div><h2 className="text-xl font-semibold">Vamos a preparar tu expediente</h2><p className="mt-2 text-slate-600">Comenzamos con emisión GMM para persona física. Reúne los datos y documentos; tu administrativo revisará el contenido antes de continuar.</p><button onClick={() => choose(null)} disabled={!editable} className={button + ' mt-4'}>Comenzar con Plauto</button></div></section>}
            <div className="grid gap-6 lg:grid-cols-[270px_1fr]">
                <aside className="space-y-3">
                    <h2 className="font-semibold">{config?.can_review ? 'Bandeja de expedientes' : 'Mis solicitudes'}</h2>
                    <label className="block text-sm">Filtrar por estado<select className={field + ' mt-1'} value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Todos</option>{Object.entries(states).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
                    {partial && <p className="text-xs text-amber-800">Mostrando los 200 expedientes más recientes.</p>}
                    {!loading && !visible.length && <p className="py-4 text-sm text-slate-500">No hay expedientes en este estado.</p>}
                    {visible.map(item => <button key={item.id} disabled={busy} onClick={() => choose(item)} className={`w-full rounded-xl border p-4 text-left ${selected?.id === item.id ? 'border-sky-700 bg-sky-50' : 'border-slate-200 bg-white'}`}><span className="block font-semibold">{item.data.client_name}</span><span className="mt-1 block text-xs text-slate-600">{states[item.status]} · {item.id.slice(0, 8)}</span></button>)}
                </aside>
                {(selected || creating) && <div className="space-y-5">
                    <section className="rounded-2xl bg-white p-5 shadow-sm">
                        <div className="mb-5 flex items-center gap-3"><Image src="/plauto/plauto.png" alt="Plauto" width={44} height={52} /><div><h2 className="font-semibold">{selected ? selected.data.client_name : 'Cuéntame para quién es la solicitud'}</h2><p className="text-sm text-slate-500">Emisión GMM · Persona física{selected && ` · ${states[selected.status]}`}</p></div></div>
                        <form onSubmit={submitData} className="grid gap-4 sm:grid-cols-2">
                            {!selected && <label className="text-sm sm:col-span-2">Agente responsable<select required className={field} value={agent} disabled={!editable} onChange={e => setAgent(e.target.value)}><option value="">Selecciona un agente</option>{config?.agents.map(a => <option key={a.rfc} value={a.rfc}>{a.name} · {a.promotoria}</option>)}</select></label>}
                            <label className="text-sm">Nombre del contratante<input required minLength={2} maxLength={200} className={field} disabled={!editable} value={data.client_name} onChange={e => setData({ ...data, client_name: e.target.value })} /></label>
                            <label className="text-sm">RFC del contratante<input maxLength={13} className={field} disabled={!editable} placeholder="Puede completarse después" value={data.rfc} onChange={e => setData({ ...data, rfc: e.target.value.toUpperCase() })} /></label>
                            <label className="text-sm sm:col-span-2">Producto de la cotización<input maxLength={150} className={field} disabled={!editable} value={data.product} onChange={e => setData({ ...data, product: e.target.value })} /></label>
                            <details className="sm:col-span-2 rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer font-medium">Datos para llenar la solicitud oficial</summary><p className="my-3 text-xs text-slate-500">Confirma los nombres y apellidos por separado; Plauto no los separará por suposición.</p><div className="grid gap-3 sm:grid-cols-2">{Object.entries(identityFields).map(([key, label]) => <label className="text-sm" key={key}>{label}<input className={field} disabled={!editable} maxLength={key === 'curp' ? 18 : key === 'phone' ? 25 : 100} value={data[key as keyof typeof identityFields]} onChange={e => setData({ ...data, [key]: e.target.value })} /></label>)}</div><label className="mt-3 flex gap-2 text-sm"><input type="checkbox" checked={data.maternal_surname_not_applicable} disabled={!editable} onChange={e => setData({ ...data, maternal_surname_not_applicable: e.target.checked, maternal_surname: e.target.checked ? '' : data.maternal_surname })} />El contratante confirmó que no tiene apellido materno</label></details>
                            <label className="flex gap-2 text-sm sm:col-span-2"><input type="checkbox" disabled={!editable} checked={data.recognition} onChange={e => setData({ ...data, recognition: e.target.checked })} />Solicita reconocimiento de antigüedad</label>
                            <label className="text-sm sm:col-span-2">Contexto para la mesa<textarea rows={3} maxLength={4000} className={field} disabled={!editable} value={data.notes} onChange={e => setData({ ...data, notes: e.target.value })} /></label>
                            {config?.can_operate && <div className="sm:col-span-2"><button disabled={busy || (!!selected && !dirty)} className={button}>{busy ? 'Guardando…' : selected ? 'Guardar cambios' : 'Crear mi expediente'}</button>{selected && <p className="mt-2 text-xs text-slate-500">Cambiar datos o aportar documentos devuelve el expediente a preparación y requiere una nueva revisión.</p>}</div>}
                        </form>
                    </section>
                    {selected && <>
                        <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold">Documentos de tu solicitud</h2><p className="text-sm text-slate-600">Aportado significa recibido, todavía sin validar. Puedes leer PDF, JPG o PNG de hasta 4 MB y 30 páginas; conservamos cada versión para la revisión.</p>
                            <ul className="space-y-2 text-sm">{selected.requirements.map(name => <li key={name} className="flex justify-between gap-3 border-b border-slate-100 pb-2"><span>{name}</span><span className={selected.documents.some(d => d.kind === name) ? 'text-emerald-700' : 'text-amber-800'}>{selected.documents.some(d => d.kind === name) ? 'Aportado' : 'Falta'}</span></li>)}</ul>
                            <a href="https://www.metlife.com.mx/tramites-y-servicios/documentacion-y-solicitudes/" target="_blank" rel="noreferrer" className="inline-block text-sm underline">Consultar formatos oficiales en MetLife ↗</a>
                            {config?.can_operate && <form className="space-y-3" onSubmit={e => { e.preventDefault(); const file = fileInput.current?.files?.[0]; if (!file) return; void run(async () => { const body = new FormData(); body.set('revision', String(selected.revision)); body.set('kind', kind); body.set('document', file); save(await fetchFromApi<Case>(`/mesa-control/cases/${selected.id}/documents`, { method: 'POST', body })); if (fileInput.current) fileInput.current.value = ''; setNotice('Documento guardado.'); }); }}>
                                {!config.uploads_ready && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">La carpeta privada de documentos aún no está habilitada. Puedes guardar los datos del expediente.</p>}
                                <label className="block text-sm">Tipo de documento<select className={field} value={kind} onChange={e => setKind(e.target.value)} disabled={busy}>{[...selected.requirements, 'Documentos adicionales'].map(name => <option key={name}>{name}</option>)}</select></label>
                                <label className="block text-sm">Archivo · PDF, JPG o PNG · Hasta 25 MB<input ref={fileInput} required type="file" accept=".pdf,.jpg,.jpeg,.png" className="mt-2 block w-full text-sm" disabled={busy || !config.uploads_ready || dirty} /></label>
                                <button className={button} disabled={busy || !config.uploads_ready || dirty}>Aportar documento</button>
                            </form>}
                            {selected.documents.map(doc => <div key={doc.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3"><a className="text-sm text-sky-800 underline" href={`/api/mesa-control/cases/${selected.id}/documents/${doc.id}`}>{doc.name} · {doc.kind} · {new Date(doc.at).toLocaleDateString('es-MX')}</a><button className="text-sm underline disabled:opacity-40" disabled={busy || dirty} onClick={() => void run(async () => { setExtraction(await api<Extraction>(`/cases/${selected.id}/documents/${doc.id}/extract`, 'POST')); })}>Leer documento o escaneo</button></div>)}
                            {extraction && <div className="space-y-3 rounded-xl bg-slate-50 p-4"><h3 className="font-semibold">Datos encontrados en {extraction.document_name}</h3><p className="text-sm">{extraction.notice}</p><button type="button" className="text-sm font-semibold underline" onClick={() => { setGuideDocument({ id: extraction.document_id, name: extraction.document_name, page_start: 1 }); setQuestion('Ayúdame a completar los campos pendientes con este documento. Pregunta si hay datos ambiguos.'); }}>Usar esta lectura con Plauto</button><details><summary className="cursor-pointer text-sm">Ver texto leído por página</summary>{extraction.pages?.map(page => <div key={page.page} className="mt-3"><p className="text-xs font-semibold">Página {page.page} · {page.method.includes('ocr') ? 'OCR: comprobar contra el original' : 'Texto del PDF'}{page.partial ? ' · Vista parcial' : ''}</p><pre className="mt-1 max-h-52 overflow-auto whitespace-pre-wrap break-words text-xs">{page.text || 'No se reconoció texto. Prueba con una imagen más nítida.'}</pre><button type="button" className="mt-2 text-xs font-semibold underline" onClick={() => { setGuideDocument({ id: extraction.document_id, name: extraction.document_name, page_start: page.page }); setQuestion('Ayúdame a completar los campos pendientes con las páginas seleccionadas.'); }}>Consultar a Plauto desde la página {page.page}</button></div>)}</details>{extraction.candidates.map((candidate, index) => <div className="rounded-lg border border-slate-200 bg-white p-3" key={index}><p className="font-medium">{identityFields[candidate.field as keyof typeof identityFields] || candidate.field.toUpperCase()}: {candidate.value}</p><p className="mt-1 text-xs text-slate-600">Página {candidate.page} · {candidate.method?.includes('ocr') ? 'OCR · ' : ''}{candidate.excerpt}</p><button className="mt-2 text-sm font-semibold underline" disabled={busy || dirty || !config?.can_operate} onClick={() => void run(async () => { save(await api<Case>(`/cases/${selected.id}/documents/${extraction.document_id}/confirm-extraction`, 'POST', { revision: extraction.revision, field: candidate.field, value: candidate.value, page: candidate.page })); setNotice('Dato confirmado con referencia al documento y su página.'); })}>Confirmar que corresponde al contratante</button></div>)}</div>}
                            <div className="space-y-3 rounded-xl border border-sky-200 bg-sky-50 p-4"><h3 className="font-semibold">Borrador de solicitud MédicaLife Familiar</h3><p className="text-sm">Llena nombres, RFC, CURP, correo y teléfono confirmados sobre el formato oficial. El resto de la solicitud, declaraciones y firmas debe completarse y revisarse.</p><p className="text-xs">{config?.official_form?.version} · {config?.official_form?.notice}</p><button className={button} disabled={busy || dirty || !config?.can_operate || !config?.official_form?.can_generate} onClick={() => void run(async () => { save(await api<Case>(`/cases/${selected.id}/generate-form`, 'POST', { revision: selected.revision })); setNotice('Borrador parcial guardado en la carpeta del movimiento. Descárgalo para revisar y completar.'); })}>Generar borrador oficial</button></div>
                        </section>
                        <section className="space-y-3 rounded-2xl bg-[#e8f0f5] p-5"><h2 className="font-semibold">Completa la solicitud con Plauto</h2>{selected.form_progress && <div className="space-y-3 rounded-xl bg-white p-4"><p className="text-sm font-medium">{selected.form_progress.supported ? `${selected.form_progress.filled_count} de ${selected.form_progress.mapped_count} campos del llenado parcial resueltos` : 'Confirma el producto para comenzar la guía'}</p><p className="text-sm">{selected.form_progress.next_question}</p>{!!selected.form_progress.pending_fields.length && <p className="text-xs text-slate-600">Por completar: {selected.form_progress.pending_fields.map(f => f.label).join(', ')}. Algunos datos dependen del caso.</p>}<button type="button" className="text-sm font-semibold underline" disabled={busy} onClick={() => setQuestion('Guíame con el siguiente campo pendiente.')}>Ayúdame con el siguiente campo</button><details><summary className="cursor-pointer text-sm font-medium">Secciones que deben completarse en el formato</summary><p className="mt-2 text-xs text-slate-600">Capturar todos los campos anteriores no completa toda la solicitud. Estas secciones todavía se llenan y revisan directamente en el formato.</p>{selected.form_progress.manual_sections.map(section => <div key={section.id} className="mt-3"><h3 className="text-sm font-medium">{section.title} · Página(s) {section.pages}</h3><p className="text-xs text-slate-600">{section.question}</p></div>)}</details></div>}{guideDocument && <p className="text-sm">Documento seleccionado: {guideDocument.name}. Plauto usará hasta cinco páginas desde la página {guideDocument.page_start}. <button type="button" className="underline" onClick={() => setGuideDocument(null)}>Quitar contexto</button></p>}<p className="text-sm text-slate-600">Te ayudo con los requisitos y el siguiente paso. Puedes leer PDFs, fotos y escaneos y confirmar su procedencia; el borrador oficial solo usa datos que hayas guardado.</p><form className="flex gap-2" onSubmit={e => { e.preventDefault(); void run(async () => { const result = await api<{ answer: string; proposal?: Proposal }>(`/cases/${selected.id}/guide`, 'POST', { message: question, field_key: selected.form_progress?.next_field || '', document_id: guideDocument?.id || '', page_start: guideDocument?.page_start || 1 }); setAnswer(result.answer); setProposal(result.proposal || null); }); }}><input aria-label="Pregunta para Plauto" required maxLength={2000} className={field} placeholder="¿Qué falta para enviar a revisión?" value={question} onChange={e => setQuestion(e.target.value)} disabled={busy} /><button className={button} disabled={busy}>Consultar</button></form>{answer && <p aria-live="polite" className="whitespace-pre-wrap text-sm leading-relaxed">{answer}</p>}{proposal && <div className="space-y-3 rounded-xl border border-sky-200 bg-white p-4"><h3 className="font-semibold">Datos propuestos · Pendientes de confirmar</h3>{proposal.source_document && <div className="text-xs text-slate-600"><p>Documento consultado: {proposal.source_document}</p>{proposal.evidence?.map(e => <p key={e.field}>{identityFields[e.field as keyof typeof identityFields] || e.field}: {e.value} · Página {e.page}{e.method.includes('ocr') ? ' · Revisar OCR' : ''}</p>)}</div>}<dl className="space-y-1 text-sm"><div><dt className="inline font-semibold">Contratante: </dt><dd className="inline">{proposal.data.client_name}</dd></div><div><dt className="inline font-semibold">RFC: </dt><dd className="inline">{proposal.data.rfc || 'Pendiente'}</dd></div><div><dt className="inline font-semibold">Producto: </dt><dd className="inline">{proposal.data.product || 'Pendiente'}</dd></div><div><dt className="inline font-semibold">Antigüedad: </dt><dd className="inline">{proposal.data.recognition ? 'Sí' : 'No'}</dd></div><div><dt className="inline font-semibold">Sin apellido materno: </dt><dd className="inline">{proposal.data.maternal_surname_not_applicable ? 'Confirmado por el usuario' : 'No marcado'}</dd></div><div><dt className="inline font-semibold">Contexto: </dt><dd className="inline whitespace-pre-wrap">{proposal.data.notes || 'Sin notas'}</dd></div>{Object.entries(identityFields).map(([key, label]) => <div key={key}><dt className="inline font-semibold">{label}: </dt><dd className="inline">{proposal.data[key as keyof typeof identityFields] || 'Pendiente'}</dd></div>)}</dl><p className="text-xs text-slate-500">Confirmar guarda estos datos y devuelve el expediente a preparación.</p><div className="flex gap-3"><button className={button} disabled={busy || dirty || !config?.can_operate} onClick={() => void run(async () => { save(await api<Case>(`/cases/${proposal.case_id}`, 'PATCH', { revision: proposal.revision, data: proposal.data })); setNotice('Datos propuestos por Plauto confirmados y guardados.'); })}>Confirmar y guardar</button><button className="underline" disabled={busy} onClick={() => setProposal(null)}>Descartar</button></div></div>}</section>
                        <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm"><h2 className="font-semibold">Revisión administrativa</h2>
                            <p className="text-sm text-slate-600">{states[selected.status]}. La validación de mesa no equivale al ingreso ni a la aceptación de MetLife.</p>
                            {!!selected.missing.length && <p className="text-sm text-amber-800">Falta completar: {selected.missing.join(', ')}.</p>}
                            {dirty && <p className="text-sm text-amber-800">Guarda los cambios antes de continuar.</p>}
                            {config?.can_operate && ['draft', 'correction'].includes(selected.status) && <button className={button} disabled={busy || dirty || !!selected.missing.length} onClick={() => transition('submit')}>Enviar a revisión</button>}
                            {config?.can_review && selected.status === 'submitted' && <button className={button} disabled={busy || dirty} onClick={() => transition('claim')}>Tomar revisión</button>}
                            {config?.can_review && selected.status === 'reviewing' && <div className="space-y-3"><p className="text-xs text-slate-500">Solo el administrativo que tomó la revisión puede emitir el resultado.</p><label className="block text-sm">Resultado o corrección solicitada<textarea maxLength={2000} className={field} value={comment} onChange={e => setComment(e.target.value)} /></label><label className="block text-sm">Motivo de devolución<select className={field} value={reason} onChange={e => setReason(e.target.value)}>{config.reasons.map(r => <option key={r} value={r}>{reasons[r] || r}</option>)}</select></label><label className="block text-sm">Documento o campo afectado<input maxLength={200} className={field} value={target} onChange={e => setTarget(e.target.value)} /></label><div className="flex flex-wrap gap-3"><button className={button} disabled={busy || dirty || !comment.trim() || !target.trim()} onClick={() => transition('correct')}>Solicitar corrección</button><button className={button} disabled={busy || dirty || !comment.trim() || !!selected.missing.length} onClick={() => transition('validate')}>Validar expediente</button></div></div>}
                        </section>
                        <section className="rounded-2xl bg-white p-5"><h2 className="mb-4 font-semibold">Historial del movimiento</h2><ol className="space-y-4">{[...selected.history].reverse().map((entry, index) => <li key={`${entry.revision}-${index}`} className="border-l-2 border-slate-200 pl-4 text-sm"><p className="font-medium">{actions[entry.action] || entry.action}</p><p className="text-xs text-slate-500">{entry.actor} · {new Date(entry.at).toLocaleString('es-MX')} · Versión {entry.revision}</p>{entry.comment && <p className="mt-1 whitespace-pre-wrap">{entry.target && `${entry.target}: `}{entry.comment}{entry.reason && ` (${reasons[entry.reason] || entry.reason})`}</p>}</li>)}</ol></section>
                    </>}
                </div>}
            </div>
        </div>
    </div>;
}
