'use client';

import { useMemo, useState } from 'react';
import { AlertTriangle, ExternalLink, GitMerge, Search, X } from 'lucide-react';
import { Cliente, ClientIdentityCandidateGroup, ClientIdentityCandidatesResponse } from '@/lib/types/clientes';

interface Props {
    data: ClientIdentityCandidatesResponse;
    clients: Cliente[];
    isMerging: boolean;
    onClose: () => void;
    onMerge: (canonicalId: string, duplicateIds: string[]) => Promise<void>;
}

export function ClientIdentityModal({ data, clients, isMerging, onClose, onMerge }: Props) {
    const [mode, setMode] = useState<'suggested' | 'manual'>('suggested');
    const [selectedCanonical, setSelectedCanonical] = useState<Record<string, string>>({});
    const [manualSearch, setManualSearch] = useState('');
    const [manualStatus, setManualStatus] = useState<'all' | 'prospect' | 'identified'>('all');
    const [manualSelection, setManualSelection] = useState<string[]>([]);
    const [manualCanonical, setManualCanonical] = useState('');
    const groups = useMemo(() => data.groups, [data.groups]);
    const selectedClients = clients.filter((client) => client.id && manualSelection.includes(client.id));
    const manualResults = useMemo(() => {
        const term = manualSearch.trim().toLocaleLowerCase('es-MX');
        if (term.length < 2) return [];
        return clients.filter((client) => {
            const statusMatches = manualStatus === 'all' || client.estado_identidad === manualStatus;
            const text = [client.nombre, client.rfc, client.correo, client.telefono].filter(Boolean).join(' ').toLocaleLowerCase('es-MX');
            return statusMatches && text.includes(term);
        }).slice(0, 200);
    }, [clients, manualSearch, manualStatus]);

    const mergeGroup = async (group: ClientIdentityCandidateGroup) => {
        const canonicalId = selectedCanonical[group.group_id] || group.canonical_options[0];
        if (!canonicalId) return;
        const duplicates = group.members.map((member) => member.id).filter((id) => id !== canonicalId);
        const canonical = group.members.find((member) => member.id === canonicalId);
        if (!confirm(`¿Homologar ${duplicates.length} registro(s) dentro de ${canonical?.nombre}? Las relaciones se reasignarán y los nombres anteriores quedarán como alias.`)) return;
        await onMerge(canonicalId, duplicates);
    };

    const toggleManual = (clientId: string) => {
        setManualSelection((current) => current.includes(clientId) ? current.filter((id) => id !== clientId) : [...current, clientId]);
        if (manualCanonical === clientId) setManualCanonical('');
    };

    const mergeManual = async () => {
        const canonical = selectedClients.find((client) => client.id === manualCanonical);
        const duplicateIds = manualSelection.filter((id) => id !== manualCanonical);
        if (!canonical?.id || !canonical.rfc || duplicateIds.length === 0) return;
        if (!confirm(`¿Homologar ${duplicateIds.length} registro(s) dentro de ${canonical.nombre} (${canonical.rfc})? Esta selección fue realizada manualmente.`)) return;
        await onMerge(canonical.id, duplicateIds);
        setManualSelection([]);
        setManualCanonical('');
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 p-3 backdrop-blur-sm sm:p-6">
            <section className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-slate-50 shadow-2xl">
                <header className="flex items-start justify-between border-b bg-white p-5">
                    <div>
                        <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900"><GitMerge className="h-5 w-5 text-indigo-600" /> Homologación de clientes</h2>
                        <p className="mt-1 text-sm text-slate-600">Selecciona los registros y confirma siempre cuál será el cliente maestro con RFC.</p>
                    </div>
                    <button onClick={onClose} className="rounded-md p-1 text-slate-500 hover:bg-slate-100"><X className="h-6 w-6" /></button>
                </header>

                <nav className="flex border-b bg-white px-5">
                    <button onClick={() => setMode('suggested')} className={`border-b-2 px-4 py-3 text-sm font-bold ${mode === 'suggested' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500'}`}>Sugerencias ({data.total_groups})</button>
                    <button onClick={() => setMode('manual')} className={`border-b-2 px-4 py-3 text-sm font-bold ${mode === 'manual' ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-slate-500'}`}>Selección manual</button>
                </nav>

                {mode === 'suggested' ? (
                    <div className="overflow-y-auto p-4 sm:p-6">
                        {groups.length === 0 ? (
                            <div className="rounded-xl border bg-white p-8 text-center text-slate-600">No encontramos candidatos con las reglas automáticas actuales. Puedes usar Selección manual.</div>
                        ) : groups.map((group) => {
                            const canonicalId = selectedCanonical[group.group_id] || group.canonical_options[0] || '';
                            const canMerge = Boolean(canonicalId) && !group.conflicting_rfcs;
                            return (
                                <article key={group.group_id} className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${group.confidence === 'alta' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>Confianza {group.confidence}</span>
                                            {group.reasons.map((reason) => <span key={reason} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{reason}</span>)}
                                        </div>
                                        <button disabled={!canMerge || isMerging} onClick={() => mergeGroup(group)} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40">{isMerging ? 'Homologando…' : `Fusionar ${Math.max(0, group.members.length - 1)} registro(s)`}</button>
                                    </div>
                                    {group.conflicting_rfcs && <p className="mb-3 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-700"><AlertTriangle className="h-4 w-4" /> Hay RFC distintos. Este grupo requiere revisión manual.</p>}
                                    {!group.conflicting_rfcs && group.canonical_options.length === 0 && <p className="mb-3 flex items-center gap-2 rounded-lg bg-amber-50 p-3 text-sm font-semibold text-amber-800"><AlertTriangle className="h-4 w-4" /> Primero asigna el RFC a uno de estos prospectos.</p>}
                                    <div className="space-y-2">{group.members.map((member) => {
                                        const relationSummary = Object.entries(member.relaciones).filter(([, count]) => count > 0).map(([label, count]) => `${count} ${label}`).join(' · ');
                                        return <label key={member.id} className={`block rounded-lg border p-3 ${canonicalId === member.id ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200'}`}><div className="flex items-start gap-3"><input type="radio" name={`canonical-${group.group_id}`} disabled={!group.canonical_options.includes(member.id)} checked={canonicalId === member.id} onChange={() => setSelectedCanonical((current) => ({ ...current, [group.group_id]: member.id }))} className="mt-1" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><strong className="text-slate-900">{member.nombre}</strong>{member.rfc ? <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">RFC {member.rfc}</span> : <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">Sin RFC</span>}{member.expediente_url && <a href={member.expediente_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600">Expediente <ExternalLink className="h-3 w-3" /></a>}</div><p className="mt-1 text-xs text-slate-500">{[member.correo, member.telefono, relationSummary].filter(Boolean).join(' · ') || 'Sin relaciones registradas'}</p></div></div></label>;
                                    })}</div>
                                </article>
                            );
                        })}
                        {data.truncated && <p className="text-center text-sm text-slate-500">Se muestran los primeros {groups.length} grupos.</p>}
                    </div>
                ) : (
                    <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-4 sm:p-6">
                        <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-4">
                            <label className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-2.5 h-5 w-5 text-slate-400" /><input value={manualSearch} onChange={(event) => setManualSearch(event.target.value)} placeholder="Buscar por nombre, RFC, correo o teléfono…" className="w-full rounded-md border border-slate-300 py-2 pl-10 pr-3 text-sm" /></label>
                            <select value={manualStatus} onChange={(event) => setManualStatus(event.target.value as typeof manualStatus)} className="rounded-md border border-slate-300 px-3 py-2 text-sm"><option value="all">Clientes y prospectos</option><option value="prospect">Solo prospectos</option><option value="identified">Solo identificados</option></select>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900">
                            <span><strong>{manualSelection.length}</strong> seleccionados. Marca como maestro uno que tenga RFC.</span>
                            <button onClick={mergeManual} disabled={isMerging || !manualCanonical || manualSelection.length < 2} className="rounded-md bg-indigo-600 px-3 py-2 font-bold text-white disabled:opacity-40">{isMerging ? 'Homologando…' : `Homologar selección (${Math.max(0, manualSelection.length - 1)})`}</button>
                        </div>

                        <div className="mt-3 overflow-y-auto rounded-xl border bg-white">
                            {manualSearch.trim().length < 2 ? <p className="p-8 text-center text-sm text-slate-500">Escribe al menos dos caracteres para buscar.</p> : manualResults.length === 0 ? <p className="p-8 text-center text-sm text-slate-500">No encontramos registros con esos filtros.</p> : manualResults.map((client) => {
                                const clientId = client.id || '';
                                const checked = manualSelection.includes(clientId);
                                return <div key={clientId} className={`flex items-start gap-3 border-b p-3 last:border-b-0 ${checked ? 'bg-indigo-50' : ''}`}><input type="checkbox" checked={checked} onChange={() => toggleManual(clientId)} className="mt-1" /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><strong>{client.nombre}</strong>{client.rfc ? <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">RFC {client.rfc}</span> : <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">Prospecto sin RFC</span>}</div><p className="mt-1 text-xs text-slate-500">{[client.correo, client.telefono].filter(Boolean).join(' · ') || 'Sin datos de contacto'}</p></div>{checked && client.rfc && <label className="flex items-center gap-2 text-xs font-bold text-indigo-700"><input type="radio" name="manual-master" checked={manualCanonical === clientId} onChange={() => setManualCanonical(clientId)} /> Cliente maestro</label>}</div>;
                            })}
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}
