'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import { ArrowUp, Check, ExternalLink, FileText, Loader2, MessageCircle, Minus, Search, ShieldCheck, Sparkles, Trash2, X } from 'lucide-react';
import styles from './Plauto.module.css';

type Status = { available: boolean; chat_ready: boolean; legacy_ready: boolean; username: string };
type Source = { id: string; title: string; source: string; url: string };
type Contact = { correo: string; telefono: string };
type Proposal = { id: string; title: string; before: Contact; after: Contact; status: string };
type ClientMatch = { id: string; nombre: string; rfc: string };
type Message = { id: string; role: 'user' | 'assistant'; text: string; sources?: Source[]; proposals?: Proposal[]; clients?: ClientMatch[] };
type Answer = { answer: string; sources: Source[]; proposals: Proposal[]; clients?: ClientMatch[] };

async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`/api/plauto/${path}`, {
        method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', signal,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === 'string' ? data.detail : 'No fue posible completar la consulta. Inténtalo de nuevo.');
    }
    return response.json();
}

function Avatar({ thinking = false }: { thinking?: boolean }) {
    return <span className={`${styles.avatar} ${thinking ? styles.thinking : ''}`} aria-hidden="true">
        <Image src="/plauto/plauto.png" alt="" width={66} height={77} className={styles.penguin} />
        <span className={styles.spark}>✦</span>
    </span>;
}

function safeSource(url: string) {
    if (url === '/clientes') return url;
    try {
        const parsed = new URL(url);
        return parsed.protocol === 'https:' && parsed.hostname === 'drive.google.com' ? parsed.href : null;
    } catch { return null; }
}

export function Plauto() {
    const pathname = usePathname();
    const isPublic = ['/login', '/olvide-password', '/restablecer-password', '/cambiar-password', '/sin-acceso'].includes(pathname)
        || pathname.startsWith('/solicitud-datos/') || pathname.startsWith('/encuesta/');
    return isPublic || pathname === '/mesa-control' ? null : <PlautoSession pathname={pathname} />;
}

function PlautoSession({ pathname }: { pathname: string }) {
    const [status, setStatus] = useState<Status | null>(null);
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [draft, setDraft] = useState('');
    const [busy, setBusy] = useState(false);
    const [actionBusy, setActionBusy] = useState<string | null>(null);
    const [error, setError] = useState('');
    const [searchOnly, setSearchOnly] = useState(false);
    const input = useRef<HTMLTextAreaElement>(null);
    const bottom = useRef<HTMLDivElement>(null);
    const launcher = useRef<HTMLButtonElement>(null);
    const abort = useRef<AbortController | null>(null);
    const owner = useRef('');
    const submitting = useRef(false);
    const confirming = useRef(false);

    useEffect(() => {
        let active = true;
        api<Status>('status').then(data => {
            if (!active) return;
            if (owner.current && owner.current !== data.username) {
                abort.current?.abort(); setMessages([]); setDraft(''); setOpen(false);
            }
            owner.current = data.username;
            setStatus(data);
            if (!data.available) { setMessages([]); setOpen(false); }
        }).catch(() => { if (active) { setStatus(null); setMessages([]); setOpen(false); } });
        return () => { active = false; };
    }, [pathname]);

    useEffect(() => () => abort.current?.abort(), []);
    useEffect(() => { if (open) input.current?.focus(); }, [open]);
    useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest' }); }, [messages, busy, open]);

    const close = () => { setOpen(false); launcher.current?.focus(); };
    const submit = async (event?: FormEvent, text = draft) => {
        event?.preventDefault();
        const question = text.trim();
        if (!question || submitting.current) return;
        submitting.current = true; setBusy(true); setError(''); setDraft('');
        const prior = messages.filter(m => m.role === 'user').slice(-6).map(m => m.text);
        setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user' as const, text: question }].slice(-60));
        const requestOwner = owner.current;
        abort.current = new AbortController();
        try {
            // Recheck identity before carrying context across a session boundary.
            const latest = await api<Status>('status', undefined, abort.current.signal);
            if (latest.username !== requestOwner || !latest.available) {
                setMessages([]); setStatus(null); setOpen(false); return;
            }
            setStatus(latest);
            const answer = await api<Answer>('chat', { message: question, previous_questions: prior, search_only: searchOnly || !latest.chat_ready }, abort.current.signal);
            if (owner.current !== requestOwner) return;
            setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant' as const, text: answer.answer, sources: answer.sources, proposals: answer.proposals, clients: answer.clients }].slice(-60));
        } catch (err) {
            if (owner.current === requestOwner && !(err instanceof DOMException && err.name === 'AbortError')) {
                setError(err instanceof Error ? err.message : 'No se pudo completar la consulta.');
                setDraft(question);
            }
        } finally { submitting.current = false; setBusy(false); }
    };
    const documents = async (client: ClientMatch) => {
        if (submitting.current) return;
        submitting.current = true; setBusy(true); setError('');
        const requestOwner = owner.current;
        abort.current = new AbortController();
        try {
            const latest = await api<Status>('status', undefined, abort.current.signal);
            if (latest.username !== requestOwner || !latest.available) {
                setMessages([]); setStatus(null); setOpen(false); return;
            }
            const answer = await api<Answer>(`clients/${encodeURIComponent(client.id)}/documents`, undefined, abort.current.signal);
            if (owner.current !== requestOwner) return;
            setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant' as const, text: answer.answer, sources: answer.sources }].slice(-60));
        } catch (err) {
            if (owner.current === requestOwner && !(err instanceof DOMException && err.name === 'AbortError')) setError(err instanceof Error ? err.message : 'No se pudo consultar el expediente.');
        } finally { submitting.current = false; setBusy(false); }
    };
    const confirm = async (proposal: Proposal, accepted: boolean) => {
        if (confirming.current) return;
        confirming.current = true; setActionBusy(proposal.id); setError('');
        try {
            const result = await api<{ status: string }>(`actions/${proposal.id}`, { confirm: accepted });
            setMessages(current => current.map(message => ({ ...message, proposals: message.proposals?.map(p => p.id === proposal.id ? { ...p, status: result.status } : p) })));
        } catch (err) { setError(err instanceof Error ? err.message : 'No se pudo aplicar el cambio.'); }
        finally { confirming.current = false; setActionBusy(null); }
    };

    if (!status?.available) return null;
    const searching = searchOnly || !status.chat_ready;
    return <div className={styles.root}>
        {open && <section className={styles.panel} role="dialog" aria-modal="false" aria-label="Chat con Plauto" onKeyDown={event => { if (event.key === 'Escape') close(); }}>
            <header className={styles.header}>
                <div className={styles.smallAvatar}><Avatar thinking={busy} /></div>
                <div><h2>Plauto <span>✦</span></h2><p>Tu compañero en TAIICO</p></div>
                <button type="button" aria-label="Borrar conversación" title="Borrar conversación" disabled={busy || !!actionBusy} onClick={() => { setMessages([]); setError(''); setDraft(''); }}><Trash2 size={16} /></button>
                <button type="button" aria-label="Minimizar Plauto" onClick={close}><Minus size={20} /></button>
            </header>
            <div className={styles.scope}><ShieldCheck size={13} /><span>Sólo expedientes autorizados para tu usuario</span></div>
            {!status.chat_ready && <div className={styles.notice}>El chat está pendiente de activación. Ya puedes buscar clientes y abrir sus documentos por nombre, RFC o póliza.</div>}
            {status.chat_ready && !status.legacy_ready && <div className={styles.notice}>Drive antiguo pendiente de conexión. Plauto indicará qué fuentes pudo consultar.</div>}
            <div className={styles.messages} role="log" aria-label="Conversación" aria-live="polite" aria-relevant="additions text">
                {messages.length === 0 && <div className={styles.welcome}>
                    <span className={styles.eyebrow}>MENOS VUELTAS. MÁS CLARIDAD.</span>
                    <h3>Hola, soy Plauto.</h3><p>{searching ? 'Encontremos ese expediente.' : '¿Qué resolvemos hoy?'}</p>
                    <div className={styles.suggestions}>
                        {(searching ? ['Buscar por nombre del cliente', 'Buscar por número de póliza'] : ['Encuentra el expediente de…', '¿Qué documentos tiene…?', 'Ayúdame a actualizar un contacto']).map(text => <button key={text} type="button" onClick={() => { setDraft(searching ? '' : text); input.current?.focus(); }}><Search size={15} />{text}<span>↗</span></button>)}
                    </div>
                    <p className={styles.hint}>Consulta las fuentes antes de tomar una decisión sobre una póliza o siniestro.</p>
                </div>}
                {messages.map(message => <article key={message.id} className={`${styles.message} ${message.role === 'user' ? styles.user : styles.assistant}`}>
                    <span className={styles.author}>{message.role === 'user' ? 'Tú' : 'Plauto'}</span>
                    <div className={styles.text}>{message.text}</div>
                    {!!message.clients?.length && <div className={styles.suggestions}>{message.clients.map(client => <button key={client.id} type="button" disabled={busy} onClick={() => documents(client)}><Search size={15} /><span>{client.nombre}<small className={styles.clientRfc}>{client.rfc || 'Sin RFC'}</small></span><span>Ver documentos ↗</span></button>)}</div>}
                    {!!message.sources?.length && <div className={styles.sources}><span>Fuentes consultadas</span>{message.sources.map(source => {
                        const href = safeSource(source.url);
                        return href && <a key={source.id} href={href} target={href.startsWith('https:') ? '_blank' : undefined} rel="noopener noreferrer"><FileText size={15} /><span><strong>{source.title}</strong><small>{source.source}</small></span><ExternalLink size={12} /></a>;
                    })}</div>}
                    {message.proposals?.map(proposal => <div className={styles.proposal} key={proposal.id}>
                        <strong>{proposal.title}</strong>
                        {(['correo', 'telefono'] as const).filter(key => proposal.before[key] !== proposal.after[key]).map(key => <div className={styles.change} key={key}><span>{key === 'correo' ? 'Correo' : 'Teléfono'}</span><del>{proposal.before[key] || 'Sin dato'}</del><b>{proposal.after[key] || 'Se eliminará este dato'}</b></div>)}
                        {proposal.status === 'pending' ? <div className={styles.actions}><button disabled={!!actionBusy} onClick={() => confirm(proposal, true)}>{actionBusy === proposal.id ? <Loader2 size={14} className={styles.spin} /> : <Check size={14} />}Confirmar cambio</button><button disabled={!!actionBusy} onClick={() => confirm(proposal, false)}>Cancelar</button></div> : <p>{proposal.status === 'completed' ? 'Cambio guardado y registrado en auditoría.' : 'Propuesta cancelada.'}</p>}
                    </div>)}
                </article>)}
                {busy && <div className={styles.working}><span /><span /><span /><small>Plauto está consultando…</small></div>}
                <div ref={bottom} />
            </div>
            {error && <div className={styles.error} role="alert">{error}<button type="button" aria-label="Cerrar aviso" onClick={() => setError('')}><X size={14} /></button></div>}
            <form className={styles.composer} onSubmit={submit}>
                {status.chat_ready && <div className={styles.modes}><button type="button" aria-pressed={!searchOnly} onClick={() => setSearchOnly(false)}><Sparkles size={12} />Conversar</button><button type="button" aria-pressed={searchOnly} onClick={() => setSearchOnly(true)}><Search size={12} />Buscar cliente</button></div>}
                <div className={styles.inputRow}><textarea ref={input} value={draft} maxLength={4000} rows={2} onChange={event => setDraft(event.target.value)} placeholder={searching ? 'Nombre, RFC o número de póliza…' : 'Pregúntale a Plauto…'} aria-label="Mensaje para Plauto" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(); } }} /><button type="submit" aria-label="Enviar mensaje" disabled={busy || !draft.trim()}>{busy ? <Loader2 size={19} className={styles.spin} /> : <ArrowUp size={20} />}</button></div>
                <p>Los cambios requieren tu confirmación.</p>
            </form>
        </section>}
        <button ref={launcher} type="button" className={`${styles.launcher} ${open ? styles.launcherOpen : ''}`} onClick={() => setOpen(!open)} aria-label={open ? 'Cerrar chat con Plauto' : 'Abrir chat con Plauto'} aria-expanded={open}>
            {open ? <MessageCircle size={26} /> : <Avatar thinking={busy} />}
            {!open && <span className={styles.label}>Plauto</span>}
            {!open && <span className={styles.online} />}
        </button>
    </div>;
}
