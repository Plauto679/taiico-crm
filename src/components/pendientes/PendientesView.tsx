'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, Mail, Plus } from 'lucide-react';
import { DataTable } from '@/components/ui/DataTable';
import { CommercialPendingData, PendingRow, PendingSourceData } from '@/lib/types/pendientes';
import { exportToExcel } from '@/lib/utils/export';
import { getPendingSource } from '@/modules/pendientes/service';
import { formatHistoryDate, PendingHistoryModal } from './PendingHistoryModal';
import { RegisterPendingModal } from './RegisterPendingModal';
import { PendingReportModal } from './PendingReportModal';
import { CommercialPendingPanel } from './CommercialPendingPanel';

interface PendientesViewProps {
    emisionServicios: PendingSourceData;
    siniestros: PendingSourceData;
    commercial: CommercialPendingData;
}

export function PendientesView({ emisionServicios, siniestros, commercial }: PendientesViewProps) {
    const initialTab = !emisionServicios.load_error
        ? 'emision-servicios'
        : !siniestros.load_error
            ? 'siniestros'
            : 'commercial';
    const [activeTab, setActiveTab] = useState<'emision-servicios' | 'siniestros' | 'commercial'>(initialTab);
    const [selectedRow, setSelectedRow] = useState<PendingRow | null>(null);
    const [emisionData, setEmisionData] = useState(emisionServicios);
    const [siniestrosData, setSiniestrosData] = useState(siniestros);
    const [showRegisterModal, setShowRegisterModal] = useState(false);
    const [showReportModal, setShowReportModal] = useState(false);
    const [visibleRows, setVisibleRows] = useState<PendingRow[]>(
        initialTab === 'siniestros' ? siniestros.rows : emisionServicios.rows,
    );
    const [notice, setNotice] = useState<string | null>(null);
    const tabularSource = activeTab === 'commercial' ? 'emision-servicios' : activeTab;
    const activeData = tabularSource === 'emision-servicios' ? emisionData : siniestrosData;
    const canOperate = activeData.access.can_operate;
    const canOperateCommercial = emisionData.access.can_operate || siniestrosData.access.can_operate;
    const inconsistencyCount = (
        emisionData.inconsistencies.length + siniestrosData.inconsistencies.length
    );

    const columns = useMemo(() => [
        ...activeData.core_headers.map((header) => ({
            header,
            accessorKey: (row: PendingRow) => formatSummaryValue(header, row.summary[header]) || '—',
        })),
        {
            header: 'Última actualización',
            accessorKey: (row: PendingRow) => row.latest_update.update
                ? `(${formatHistoryDate(row.latest_update.date)}) ${row.latest_update.update}`
                : '—',
        },
    ], [activeData]);

    useEffect(() => {
        if (!notice) return;
        const timeout = window.setTimeout(() => setNotice(null), 3500);
        return () => window.clearTimeout(timeout);
    }, [notice]);

    const handleProcessedDataChange = useCallback((rows: PendingRow[]) => {
        setVisibleRows(rows);
    }, []);

    const selectTab = (tab: 'emision-servicios' | 'siniestros') => {
        setActiveTab(tab);
        setVisibleRows(tab === 'emision-servicios' ? emisionData.rows : siniestrosData.rows);
    };

    const downloadExcel = () => {
        const rows = visibleRows.map((row) => ({
            ...Object.fromEntries(
                activeData.core_headers.map((header) => [header, formatSummaryValue(header, row.summary[header])]),
            ),
            'Última actualización': row.latest_update.update
                ? `(${formatHistoryDate(row.latest_update.date)}) ${row.latest_update.update}`
                : '',
        }));
        const date = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'America/Mexico_City',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).format(new Date());
        exportToExcel(rows, `Pendientes-${activeTab}-${date}.xlsx`);
    };

    const handleCreated = (row: PendingRow) => {
        if (tabularSource === 'emision-servicios') {
            setEmisionData((current) => ({ ...current, rows: [...current.rows, row] }));
        } else {
            setSiniestrosData((current) => ({ ...current, rows: [...current.rows, row] }));
        }
        setShowRegisterModal(false);
        setNotice('Pendiente registrado correctamente. Se notificará al responsable asignado.');
    };

    const handleUpdated = (row: PendingRow) => {
        const replaceRow = (current: PendingSourceData) => ({
            ...current,
            rows: current.rows.map((item) => item.id === row.id ? row : item),
        });
        if (tabularSource === 'emision-servicios') setEmisionData(replaceRow);
        else setSiniestrosData(replaceRow);
        setSelectedRow(row);
    };

    const handleDeleted = async () => {
        const refreshed = await getPendingSource(tabularSource);
        if (tabularSource === 'emision-servicios') setEmisionData(refreshed);
        else setSiniestrosData(refreshed);
        setVisibleRows(refreshed.rows);
        setSelectedRow(null);
        setNotice('Pendiente eliminado correctamente. El expediente de Drive se conservó.');
    };

    return (
        <>
            <div className="flex h-full min-h-0 max-w-full flex-col gap-4">
                {activeData.access.central_admin && inconsistencyCount > 0 && (
                    <div className="flex flex-none items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900">
                        <AlertTriangle className="h-5 w-5" />
                        {inconsistencyCount} registros necesitan asignación de promotoría o agente.
                    </div>
                )}
                <div className="flex flex-none flex-wrap items-center justify-between gap-4 border-b border-gray-300">
                    <div className="flex gap-2">
                        <button
                            type="button"
                            onClick={() => selectTab('emision-servicios')}
                            className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'emision-servicios' ? 'border-white text-white' : 'border-transparent text-blue-100 hover:text-white'}`}
                        >
                            Emisión y Servicios {emisionData.load_error && <AlertTriangle className="ml-1 inline h-4 w-4" />}
                        </button>
                        <button
                            type="button"
                            onClick={() => selectTab('siniestros')}
                            className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'siniestros' ? 'border-white text-white' : 'border-transparent text-blue-100 hover:text-white'}`}
                        >
                            Siniestros {siniestrosData.load_error && <AlertTriangle className="ml-1 inline h-4 w-4" />}
                        </button>
                        <button
                            type="button"
                            onClick={() => { setActiveTab('commercial'); setSelectedRow(null); setShowRegisterModal(false); }}
                            className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'commercial' ? 'border-white text-white' : 'border-transparent text-blue-100 hover:text-white'}`}
                        >
                            Comerciales
                        </button>
                    </div>
                    <div className="flex items-center gap-3">
                        <p className="text-sm text-blue-100">{activeTab === 'commercial' ? commercial.rows.length : activeData.rows.length} registros</p>
                        {activeTab !== 'commercial' && !activeData.load_error && <>
                        <button type="button" onClick={downloadExcel} className="inline-flex items-center gap-2 rounded-lg border border-white/60 px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">
                            <Download className="h-4 w-4" /> Descargar Excel
                        </button>
                        {canOperate && <>
                            <button type="button" onClick={() => setShowReportModal(true)} className="inline-flex items-center gap-2 rounded-lg border border-white/60 px-3 py-2 text-sm font-semibold text-white hover:bg-white/10">
                                <Mail className="h-4 w-4" /> Enviar informe
                            </button>
                            <button type="button" onClick={() => setShowRegisterModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-blue-700 shadow-sm hover:bg-blue-50">
                                <Plus className="h-4 w-4" /> Registrar Pendiente
                            </button>
                        </>}
                        </>}
                    </div>
                </div>

                {activeTab === 'commercial' ? (
                    <CommercialPendingPanel initialData={commercial} canOperate={canOperateCommercial} />
                ) : activeData.load_error ? (
                    <div role="alert" className="flex min-h-0 flex-1 items-center justify-center rounded-lg border border-amber-200 bg-amber-50 p-8 text-center shadow">
                        <div className="max-w-xl text-amber-900">
                            <AlertTriangle className="mx-auto mb-3 h-10 w-10" />
                            <h2 className="text-lg font-bold">No fue posible cargar {activeData.title}</h2>
                            <p className="mt-2 text-sm">{activeData.load_error}</p>
                        </div>
                    </div>
                ) : (
                    <div className="min-h-0 min-w-0 flex-1 overflow-hidden rounded-lg bg-white shadow">
                        <DataTable key={activeTab} data={activeData.rows} columns={columns} filterMode="multi-select" onRowClick={setSelectedRow} onProcessedDataChange={handleProcessedDataChange} className="h-full max-w-full overflow-auto border-0 shadow-none" />
                    </div>
                )}
                {activeTab !== 'commercial' && !activeData.load_error && <p className="flex-none text-sm text-blue-100">
                    Haz clic en un registro para consultar el historial completo de actualizaciones.
                </p>}
            </div>

            {notice && (
                <div role="status" className="fixed right-4 top-4 z-[70] flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800 shadow-lg">
                    <CheckCircle2 className="h-5 w-5" />
                    {notice}
                </div>
            )}
            {selectedRow && <PendingHistoryModal key={`${tabularSource}:${selectedRow.id}`} row={selectedRow} source={tabularSource} access={activeData.access} onUpdated={handleUpdated} onDeleted={handleDeleted} onClose={() => setSelectedRow(null)} />}
            {showRegisterModal && (
                <RegisterPendingModal
                    source={tabularSource}
                    onClose={() => setShowRegisterModal(false)}
                    onCreated={handleCreated}
                    access={activeData.access}
                />
            )}
            {showReportModal && <PendingReportModal onClose={() => setShowReportModal(false)} />}
        </>
    );
}

function formatSummaryValue(header: string, value = ''): string {
    const normalizedHeader = header
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim()
        .toLocaleLowerCase('es-MX');
    if (normalizedHeader === 'monto') {
        if (!value.trim()) return '';
        const amount = Number(value.replace(/[$,\s]/g, ''));
        if (!Number.isFinite(amount)) return value;
        return new Intl.NumberFormat('es-MX', {
            style: 'currency',
            currency: 'MXN',
            minimumFractionDigits: 2,
        }).format(amount);
    }
    if (normalizedHeader !== 'fecha inicio') return value;

    const isoDate = value.trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (!isoDate) return value;
    return `${isoDate[1]}-${isoDate[2].padStart(2, '0')}-${isoDate[3].padStart(2, '0')}`;
}
