'use client';

import { X } from 'lucide-react';
import { PendingRow } from '@/lib/types/pendientes';

interface PendingHistoryModalProps {
    row: PendingRow | null;
    onClose: () => void;
}

export function PendingHistoryModal({ row, onClose }: PendingHistoryModalProps) {
    if (!row) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="max-h-[90vh] w-full max-w-3xl overflow-hidden rounded-xl bg-white shadow-xl">
                <div className="flex items-start justify-between border-b px-6 py-4">
                    <div>
                        <h2 className="text-xl font-semibold text-gray-900">Detalle del pendiente</h2>
                        <p className="mt-1 text-sm text-gray-500">Fila {row.source_row} del archivo canónico</p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                        aria-label="Cerrar detalle"
                    >
                        <X className="h-6 w-6" />
                    </button>
                </div>

                <div className="max-h-[calc(90vh-88px)] overflow-y-auto p-6">
                    <dl className="grid grid-cols-1 gap-4 rounded-lg bg-gray-50 p-4 sm:grid-cols-2">
                        {Object.entries(row.summary).map(([label, value]) => (
                            <div key={label}>
                                <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</dt>
                                <dd className="mt-1 text-sm text-gray-900">{value || '—'}</dd>
                            </div>
                        ))}
                    </dl>

                    <h3 className="mb-3 mt-6 text-lg font-semibold text-gray-900">Historial de actualizaciones</h3>
                    {row.history.length === 0 ? (
                        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-500">
                            No hay actualizaciones registradas.
                        </p>
                    ) : (
                        <ol className="space-y-3 border-l-2 border-blue-200 pl-5">
                            {[...row.history].reverse().map((entry, index) => (
                                <li key={`${entry.date}-${index}`} className="relative rounded-lg border bg-white p-4 shadow-sm">
                                    <span className="absolute -left-[1.72rem] top-5 h-3 w-3 rounded-full bg-blue-600 ring-4 ring-white" />
                                    <p className="text-sm font-semibold text-blue-700">{entry.date}</p>
                                    <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{entry.update}</p>
                                </li>
                            ))}
                        </ol>
                    )}
                </div>
            </div>
        </div>
    );
}
