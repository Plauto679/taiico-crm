'use client';

import { useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { RenovacionGMM, RenovacionVida, RenovacionSura } from '@/lib/types/renovaciones';
import { exportToExcel } from '@/lib/utils/export';
import { updateRenewalStatus } from '@/modules/renovaciones/service';
import { EditStatusModal } from './EditStatusModal';

interface RenovacionesViewProps {
    vidaRenewals?: RenovacionVida[];
    gmmRenewals?: RenovacionGMM[];
    suraRenewals?: RenovacionSura[];
    insurer: string;
}

export function RenovacionesView({ vidaRenewals = [], gmmRenewals = [], suraRenewals = [], insurer }: RenovacionesViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');
    const [selectedRow, setSelectedRow] = useState<any>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    const handleExport = () => {
        let data: any[] = [];
        let prefix = '';

        if (insurer === 'Metlife') {
            data = activeTab === 'VIDA' ? vidaRenewals : gmmRenewals;
            prefix = `Renovaciones_Metlife_${activeTab}`;
        } else if (insurer === 'SURA') {
            data = suraRenewals;
            prefix = `Renovaciones_SURA`;
        }

        const fileName = `${prefix}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    const handleRowClick = (row: any) => {
        setSelectedRow(row);
        setIsModalOpen(true);
    };

    const handleSaveStatus = async (newStatus: string) => {
        if (!selectedRow) return;

        let type = 'ALL';
        let id = '';

        if (insurer === 'Metlife') {
            type = activeTab;
            id = activeTab === 'VIDA' ? selectedRow.POLIZA_ACTUAL : selectedRow.NPOLIZA;
        } else if (insurer === 'SURA') {
            type = 'ALL';
            id = selectedRow.POLIZA;
        }

        await updateRenewalStatus(insurer, type, id, newStatus);

        // Optimistically update the UI (or trigger a refresh if we had one)
        // For now, we update the local object so it reflects in the table immediately if re-rendered
        // But since data comes from props, we rely on the page refresh or we can mutate the prop data (not ideal but works for simple cases)
        // A better way is to use router.refresh() from next/navigation but we are in a client component.
        // Let's just update the selectedRow object which is a reference to the data item
        selectedRow.ESTATUS_DE_RENOVACION = newStatus;
    };

    const vidaColumns = [
        { header: 'Póliza Actual', accessorKey: 'POLIZA_ACTUAL' as keyof RenovacionVida },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionVida },
        { header: 'Inicio Vigencia', accessorKey: 'INI_VIG' as keyof RenovacionVida },
        { header: 'Fin Vigencia', accessorKey: 'FIN_VIG' as keyof RenovacionVida },
        { header: 'Forma Pago', accessorKey: 'FORMA_PAGO' as keyof RenovacionVida },
        { header: 'Conducto Cobro', accessorKey: 'CONDUCTO_COBRO' as keyof RenovacionVida },
        {
            header: 'Prima Anual',
            accessorKey: (row: RenovacionVida) => {
                if (row.PRIMA_ANUAL === undefined || row.PRIMA_ANUAL === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA_ANUAL);
            }
        },
        {
            header: 'Prima Modal',
            accessorKey: (row: RenovacionVida) => {
                if (row.PRIMA_MODAL === undefined || row.PRIMA_MODAL === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA_MODAL);
            }
        },
        { header: 'Pagado Hasta', accessorKey: 'PAGADO_HASTA' as keyof RenovacionVida },
        { header: 'Estatus Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionVida }
    ];

    const gmmColumns = [
        { header: 'N Póliza', accessorKey: 'NPOLIZA' as keyof RenovacionGMM },
        { header: 'Póliza Origen', accessorKey: 'POLORIG' as keyof RenovacionGMM },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionGMM },
        { header: 'Fin Vigencia', accessorKey: 'FFINVIG' as keyof RenovacionGMM },
        {
            header: 'Prima',
            accessorKey: (row: RenovacionGMM) => {
                if (row['PRIMA.1'] === undefined || row['PRIMA.1'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['PRIMA.1']);
            }
        },
        {
            header: 'IVA',
            accessorKey: (row: RenovacionGMM) => {
                if (row.IVA === undefined || row.IVA === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.IVA);
            }
        },
        { header: 'Asegurado', accessorKey: 'NOMBREL' as keyof RenovacionGMM },
        {
            header: 'Deducible',
            accessorKey: (row: RenovacionGMM) => {
                if (row.DEDUCIBLE === undefined || row.DEDUCIBLE === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.DEDUCIBLE);
            }
        },
        { header: 'Pagado Hasta', accessorKey: 'PAGADOHASTA' as keyof RenovacionGMM },
        {
            header: 'Coaseguro',
            accessorKey: (row: RenovacionGMM) => {
                if (row.COASEGURO === undefined || row.COASEGURO === null) return '-';
                return `${(row.COASEGURO * 100).toFixed(0)}%`;
            }
        },
        { header: 'Estatus Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionGMM }
    ];

    const suraColumns = [
        { header: 'Póliza', accessorKey: 'POLIZA' as keyof RenovacionSura },
        { header: 'Nombre', accessorKey: 'NOMBRE' as keyof RenovacionSura },
        { header: 'Inicio Vigencia', accessorKey: 'INICIO VIGENCIA' as keyof RenovacionSura },
        { header: 'Fin Vigencia', accessorKey: 'FIN VIGENCIA' as keyof RenovacionSura },
        { header: 'Ramo', accessorKey: 'RAMO' as keyof RenovacionSura },
        {
            header: 'Prima',
            accessorKey: (row: RenovacionSura) => {
                if (row.PRIMA === undefined || row.PRIMA === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA);
            }
        },
        { header: 'Periodicidad', accessorKey: 'PERIODICIDAD_PAGO' as keyof RenovacionSura },
        { header: 'Prospectador', accessorKey: 'PROSPECTADOR' as keyof RenovacionSura },
        { header: 'Estatus', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionSura },
    ];

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex items-center justify-between border-b pb-2 flex-none">
                <div className="flex space-x-4">
                    {insurer === 'Metlife' && (
                        <>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'VIDA' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500'}`}
                                onClick={() => setActiveTab('VIDA')}
                            >
                                Vida
                            </button>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'GMM' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500'}`}
                                onClick={() => setActiveTab('GMM')}
                            >
                                GMM
                            </button>
                        </>
                    )}
                    {insurer === 'SURA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-blue-600 text-blue-600">
                            SURA Renovaciones
                        </span>
                    )}
                </div>
                <button
                    onClick={handleExport}
                    className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                    Exportar Excel
                </button>
            </div>

            <div className="flex-1 min-h-0 overflow-hidden">
                {insurer === 'Metlife' ? (
                    activeTab === 'VIDA' ? (
                        <DataTable
                            data={vidaRenewals}
                            columns={vidaColumns}
                            className="h-full overflow-auto"
                            onRowClick={handleRowClick}
                        />
                    ) : (
                        <DataTable
                            data={gmmRenewals}
                            columns={gmmColumns}
                            className="h-full overflow-auto"
                            onRowClick={handleRowClick}
                        />
                    )
                ) : (
                    <DataTable
                        data={suraRenewals}
                        columns={suraColumns}
                        className="h-full overflow-auto"
                        onRowClick={handleRowClick}
                    />
                )}
            </div>

            {selectedRow && (
                <EditStatusModal
                    isOpen={isModalOpen}
                    onClose={() => setIsModalOpen(false)}
                    onSave={handleSaveStatus}
                    currentStatus={selectedRow.ESTATUS_DE_RENOVACION}
                    policyNumber={
                        insurer === 'Metlife'
                            ? (activeTab === 'VIDA' ? selectedRow.POLIZA_ACTUAL : selectedRow.NPOLIZA)
                            : selectedRow.POLIZA
                    }
                    insurer={insurer}
                />
            )}
        </div>
    );
}
