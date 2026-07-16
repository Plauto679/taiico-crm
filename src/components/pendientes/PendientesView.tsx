'use client';

import { useMemo, useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { PendingRow, PendingSourceData } from '@/lib/types/pendientes';
import { PendingHistoryModal } from './PendingHistoryModal';

interface PendientesViewProps {
    emisionServicios: PendingSourceData;
    siniestros: PendingSourceData;
}

export function PendientesView({ emisionServicios, siniestros }: PendientesViewProps) {
    const [activeTab, setActiveTab] = useState<'emision-servicios' | 'siniestros'>('emision-servicios');
    const [selectedRow, setSelectedRow] = useState<PendingRow | null>(null);
    const activeData = activeTab === 'emision-servicios' ? emisionServicios : siniestros;

    const columns = useMemo(() => [
        ...activeData.core_headers.map((header) => ({
            header,
            accessorKey: (row: PendingRow) => row.summary[header] || '—',
        })),
        {
            header: `Última actualización (${activeData.latest_update_header})`,
            accessorKey: (row: PendingRow) => row.latest_update.update || '—',
        },
    ], [activeData]);

    return (
        <>
            <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-300">
                    <div className="flex gap-2">
                        <button
                            type="button"
                            onClick={() => setActiveTab('emision-servicios')}
                            className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'emision-servicios' ? 'border-white text-white' : 'border-transparent text-blue-100 hover:text-white'}`}
                        >
                            Emisión y Servicios
                        </button>
                        <button
                            type="button"
                            onClick={() => setActiveTab('siniestros')}
                            className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'siniestros' ? 'border-white text-white' : 'border-transparent text-blue-100 hover:text-white'}`}
                        >
                            Siniestros
                        </button>
                    </div>
                    <p className="text-sm text-blue-100">{activeData.rows.length} registros</p>
                </div>

                <div className="rounded-lg bg-white shadow">
                    <DataTable data={activeData.rows} columns={columns} onRowClick={setSelectedRow} />
                </div>
                <p className="text-sm text-blue-100">
                    Haz clic en un registro para consultar el historial completo de actualizaciones.
                </p>
            </div>

            <PendingHistoryModal row={selectedRow} onClose={() => setSelectedRow(null)} />
        </>
    );
}
