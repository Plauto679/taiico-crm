'use client';

import { useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { RenewalItem } from '@/lib/types/renovaciones';
import { exportToExcel } from '@/lib/utils/export';

interface RenovacionesViewProps {
    vidaRenewals: RenewalItem[];
    gmmRenewals: RenewalItem[];
}

export function RenovacionesView({ vidaRenewals, gmmRenewals }: RenovacionesViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    const handleExport = () => {
        const data = activeTab === 'VIDA' ? vidaRenewals : gmmRenewals;
        const fileName = `Renovaciones_${activeTab}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    const columns = [
        { header: 'Póliza', accessorKey: 'poliza' as keyof RenewalItem },
        { header: 'Contratante', accessorKey: 'contratante' as keyof RenewalItem },
        {
            header: 'Fecha Renovación',
            accessorKey: 'fechaRenovacion' as keyof RenewalItem,
        },
        { header: 'Ramo', accessorKey: 'ramo' as keyof RenewalItem },
        { header: 'Agente', accessorKey: 'agente' as keyof RenewalItem },
        { header: 'Estatus', accessorKey: 'estatus' as keyof RenewalItem },
        {
            header: 'Prima',
            accessorKey: (row: RenewalItem) => {
                if (row.prima === undefined || row.prima === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.prima);
            }
        },
    ];

    // Add Coaseguro column for GMM
    const gmmColumns = [
        ...columns,
        {
            header: 'Coaseguro',
            accessorKey: (row: RenewalItem) => {
                if (row.coaseguro === undefined || row.coaseguro === null) return '-';
                return `${(row.coaseguro * 100).toFixed(0)}%`;
            }
        }
    ];

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between border-b pb-2">
                <div className="flex space-x-4">
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
                </div>
                <button
                    onClick={handleExport}
                    className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                    Exportar Excel
                </button>
            </div>

            {activeTab === 'VIDA' ? (
                <DataTable data={vidaRenewals} columns={columns} />
            ) : (
                <DataTable data={gmmRenewals} columns={gmmColumns} />
            )}
        </div>
    );
}
