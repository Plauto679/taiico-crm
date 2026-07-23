'use client';

import { FormEvent, useState } from 'react';
import { Mail, Send, X } from 'lucide-react';
import { sendPendingReport } from '@/modules/pendientes/service';

interface PendingReportModalProps {
    onClose: () => void;
}

export function PendingReportModal({ onClose }: PendingReportModalProps) {
    const [email, setEmail] = useState('');
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const [sentTo, setSentTo] = useState('');

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setSending(true);
        setError('');
        try {
            const response = await sendPendingReport(email);
            setSentTo(response.recipient);
        } catch (caught) {
            setError(caught instanceof Error ? caught.message : 'No fue posible enviar el informe.');
        } finally {
            setSending(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
            <div className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl">
                <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
                    <div className="flex items-center gap-3">
                        <span className="rounded-full bg-blue-100 p-3 text-blue-700">
                            <Mail className="h-5 w-5" />
                        </span>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Enviar informe</h2>
                            <p className="text-sm text-slate-500">Emisión y Servicios + Siniestros</p>
                        </div>
                    </div>
                    <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar">
                        <X className="h-6 w-6" />
                    </button>
                </div>

                {sentTo ? (
                    <div className="space-y-5 px-6 py-6">
                        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
                            El informe fue enviado correctamente a <strong>{sentTo}</strong>.
                        </div>
                        <div className="flex justify-end">
                            <button type="button" onClick={onClose} className="rounded-lg bg-blue-700 px-5 py-2.5 font-semibold text-white hover:bg-blue-800">
                                Cerrar
                            </button>
                        </div>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-5 px-6 py-6">
                        <p className="text-sm leading-6 text-slate-600">
                            Se enviará una tabla resumen con los conteos Verde, Amarillo y Rojo,
                            además del detalle de los registros incluidos en cada clasificación.
                        </p>
                        <label className="block">
                            <span className="mb-2 block text-sm font-semibold text-slate-700">Correo electrónico</span>
                            <input
                                type="email"
                                required
                                autoFocus
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                placeholder="nombre@taiico.com"
                                className="w-full rounded-lg border border-slate-300 px-4 py-3 text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                            />
                        </label>
                        {error && (
                            <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>
                        )}
                        <div className="flex justify-end gap-3">
                            <button type="button" onClick={onClose} disabled={sending} className="rounded-lg border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                                Cancelar
                            </button>
                            <button type="submit" disabled={sending} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-5 py-2.5 font-semibold text-white hover:bg-blue-800 disabled:cursor-wait disabled:opacity-60">
                                <Send className="h-4 w-4" />
                                {sending ? 'Enviando…' : 'Enviar informe'}
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
}
