'use client';

import { useState, useEffect, useRef } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { RenovacionGMM, RenovacionVida, RenovacionSura } from '@/lib/types/renovaciones';
import { exportToExcel } from '@/lib/utils/export';
import { updateRenewalStatus } from '@/modules/renovaciones/service';
import { Check, X } from 'lucide-react';

interface RenovacionesViewProps {
    vidaRenewals?: RenovacionVida[];
    gmmRenewals?: RenovacionGMM[];
    suraRenewals?: RenovacionSura[];
    insurer: string;
}

// Editable Cell Component
const EditableStatusCell = ({
    value,
    row,
    insurer,
    type,
    idField
}: {
    value: string | undefined,
    row: any,
    insurer: string,
    type: string,
    idField: string
}) => {
    const [status, setStatus] = useState(value || '');
    const [isEditing, setIsEditing] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    // Sync local state if prop changes (e.g. refresh)
    useEffect(() => {
        setStatus(value || '');
    }, [value]);

    const handleSave = async () => {
        if (status !== (value || '')) {
            setIsSaving(true);
            try {
                await updateRenewalStatus(insurer, type, row[idField], status);
                console.log('Status updated');
                setIsEditing(false);
            } catch (error) {
                console.error('Failed to update status', error);
                alert('Error updating status');
            } finally {
                setIsSaving(false);
            }
        } else {
            setIsEditing(false);
        }
    };

    const handleCancel = () => {
        setStatus(value || '');
        setIsEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSave();
        } else if (e.key === 'Escape') {
            handleCancel();
        }
    };

    if (isEditing) {
        return (
            <div className="flex items-center space-x-1">
                <input
                    ref={inputRef}
                    type="text"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isSaving}
                    autoFocus
                    className="w-full min-w-[120px] bg-white border border-blue-500 rounded px-2 py-1 text-sm focus:outline-none"
                />
                <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="p-1 text-green-600 hover:bg-green-100 rounded"
                    title="Save"
                >
                    <Check size={16} />
                </button>
                <button
                    onClick={handleCancel}
                    disabled={isSaving}
                    className="p-1 text-red-600 hover:bg-red-100 rounded"
                    title="Cancel"
                >
                    <X size={16} />
                </button>
            </div>
        );
    }

    return (
        <div
            onClick={() => setIsEditing(true)}
            className="cursor-pointer hover:bg-gray-50 px-2 py-1 rounded border border-transparent hover:border-gray-200 min-h-[28px] flex items-center"
        >
            <span className={!status ? 'text-gray-400 italic' : ''}>
                {status || 'Click to edit...'}
            </span>
        </div>
    );
};

export function RenovacionesView({ vidaRenewals = [], gmmRenewals = [], suraRenewals = [], insurer }: RenovacionesViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

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
        {
            header: 'Estatus Renovación',
            accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionVida,
            cell: (info: any) => (
                <EditableStatusCell
                    value={info.getValue()}
                    row={info.row.original}
                    insurer="Metlife"
                    type="VIDA"
                    idField="POLIZA_ACTUAL"
                />
            )
        }
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
        {
            header: 'Estatus Renovación',
            accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionGMM,
            cell: (info: any) => (
                <EditableStatusCell
                    value={info.getValue()}
                    row={info.row.original}
                    insurer="Metlife"
                    type="GMM"
                    idField="NPOLIZA"
                />
            )
        }
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
        {
            header: 'Estatus',
            accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionSura,
            cell: (info: any) => (
                <EditableStatusCell
                    value={info.getValue()}
                    row={info.row.original}
                    insurer="SURA"
                    type="ALL"
                    idField="POLIZA"
                />
            )
        },
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
                        <DataTable data={vidaRenewals} columns={vidaColumns} className="h-full overflow-auto" />
                    ) : (
                        <DataTable data={gmmRenewals} columns={gmmColumns} className="h-full overflow-auto" />
                    )
                ) : (
                    <DataTable data={suraRenewals} columns={suraColumns} className="h-full overflow-auto" />
                )}
            </div>
        </div>
    );
}
