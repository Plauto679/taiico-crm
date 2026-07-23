'use client';

import { useMemo, useState } from 'react';
import { Mail, Plus } from 'lucide-react';
import { DataTable } from '@/components/ui/DataTable';
import { PendingRow, PendingSourceData } from '@/lib/types/pendientes';
import { formatHistoryDate, PendingHistoryModal } from './PendingHistoryModal';
import { RegisterPendingModal } from './RegisterPendingModal';
import { PendingReportModal } from './PendingReportModal';

interface PendientesViewProps {
    emisionServicios: PendingSourceData;
    siniestros: PendingSourceData;
}

export function PendientesView({ emisionServicios, siniestros }: PendientesViewProps) {
    const [activeTab, setActiveTab] = useState<'emision-servicios' | 'siniestros'>('emision-servicios');
    const [selectedRow, setSelectedRow] = useState<PendingRow | null>(null);
    const [emisionData, setEmisionData] = useState(emisionServicios);
    const [siniestrosData, setSiniestrosData] = useState(siniestros);
    const [showRegisterModal, setShowRegisterModal] = useState(false);
    const [showReportModal, setShowReportModal] = useState(false);
    const activeData = activeTab === 'emision-servicios' ? emisionData : siniestrosData;

    const columns = useMemo(() => [
        ...activeData.core_headers.map((header) => ({
            header,
            accessorKey: (row: PendingRow) => row.summary[header] || '—',
        })),
        {
            header: 'Última actualización',
            accessorKey: (row: PendingRow) => row.latest_update.update
                ? `(${formatHistoryDate(row.latest_update.date)}) ${row.latest_update.update}`
                : '—',
        },
    ], [activeData]);

    const handleCreated = (row: PendingRow) => {
        if (activeTab === 'emision-servicios') {
            setEmisionData((current) => ({ ...current, rows: [...current.rows, row] }));
        } else {
            setSiniestrosData((current) => ({ ...current, rows: [...current.rows, row] }));
        }
        setShowRegisterModal(false);
    };

    const handleUpdated = (row: PendingRow) => {
        const replaceRow = (current: PendingSourceData) => ({
            ...current,
            rows: current.rows.map((item) => item.id === row.id ? row : item),
        });
        if (activeTab === 'emision-servicios') setEmisionData(replaceRow);
        else setSiniestrosData(replaceRow);
        setSelectedRow(row);
    };

    return (
        <>
            <div className="flex h-full min-h-0 max-w-full flex-col gap-4">
                <div className="flex flex-none flex-wrap items-center justify-between gap-4 border-b border-gray-300">
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
                    <div className="flex items-center gap-3">
                        <p className="text-sm text-blue-100">{activeData.rows.length} registros</p>
                        <button type="button" onClick={() => setShowReportModal(true)} className="inline-flex items-center gap-2 rounded-lg border border-white/60 px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">
                            <Mail className="h-4 w-4" /> Enviar informe
                        </button>
                        <button type="button" onClick={() => setShowRegisterModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-blue-700 shadow-sm hover:bg-blue-50">
                            <Plus className="h-4 w-4" /> Registrar Pendiente
                        </button>
                    </div>
                </div>

                <div className="min-h-0 min-w-0 flex-1 overflow-hidden rounded-lg bg-white shadow">
                    <DataTable data={activeData.rows} columns={columns} onRowClick={setSelectedRow} className="h-full max-w-full overflow-auto border-0 shadow-none" />
                </div>
                <p className="flex-none text-sm text-blue-100">
                    Haz clic en un registro para consultar el historial completo de actualizaciones.
                </p>
            </div>

            {selectedRow && <PendingHistoryModal key={`${activeTab}:${selectedRow.id}`} row={selectedRow} source={activeTab} onUpdated={handleUpdated} onClose={() => setSelectedRow(null)} />}
            {showRegisterModal && (
                <RegisterPendingModal
                    source={activeTab}
                    onClose={() => setShowRegisterModal(false)}
                    onCreated={handleCreated}
                />
            )}
            {showReportModal && <PendingReportModal onClose={() => setShowReportModal(false)} />}
        </>
    );
}
