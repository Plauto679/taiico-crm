'use client';

import { useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { MetlifeVidaRaw, MetlifeGMMRaw } from '@/lib/types/metlife';
import { exportToExcel } from '@/lib/utils/export';

interface CobranzaViewProps {
    vidaData: MetlifeVidaRaw[];
    gmmData: MetlifeGMMRaw[];
}

export function CobranzaView({ vidaData, gmmData }: CobranzaViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    const handleExport = () => {
        const data = activeTab === 'VIDA' ? vidaData : gmmData;
        const fileName = `Cobranza_${activeTab}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    // Columns requested: '# de Póliza', 'Producto', 'Conducto de Cobro', 'Fecha de Pago del Recibo', 'Año de Vida Póliza', 'Prima Pagada', 'Comisión Bruto', 'Comisión Neta'
    const vidaColumns = [
        { header: '# de Póliza', accessorKey: '# de Póliza' as keyof MetlifeVidaRaw },
        { header: 'Producto', accessorKey: 'Producto' as keyof MetlifeVidaRaw },
        { header: 'Conducto de Cobro', accessorKey: 'Conducto de Cobro' as keyof MetlifeVidaRaw },
        { header: 'Fecha de Pago', accessorKey: 'Fecha de Pago del Recibo' as keyof MetlifeVidaRaw },
        { header: 'Año Póliza', accessorKey: 'Año de Vida Póliza' as keyof MetlifeVidaRaw },
        {
            header: 'Prima Pagada',
            accessorKey: (row: MetlifeVidaRaw) => {
                const val = row['Prima Pagada'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
        {
            header: 'Comisión Bruto',
            accessorKey: (row: MetlifeVidaRaw) => {
                const val = row['Comisión Bruto'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
        {
            header: 'Comisión Neta',
            accessorKey: (row: MetlifeVidaRaw) => {
                const val = row['Comisión Neta'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
    ];

    // Columns requested: '# de Póliza', 'Producto', 'Conducto de Cobro', 'Fecha de Pago del Recibo', 'Año de Vida Póliza', 'Estado', 'Prima Pagada', 'Comisión Bruto', 'Comisión Neta', 'IVA Causado'
    const gmmColumns = [
        { header: '# de Póliza', accessorKey: '# de Póliza' as keyof MetlifeGMMRaw },
        { header: 'Producto', accessorKey: 'Producto' as keyof MetlifeGMMRaw },
        { header: 'Conducto de Cobro', accessorKey: 'Conducto de Cobro' as keyof MetlifeGMMRaw },
        { header: 'Fecha de Pago', accessorKey: 'Fecha de Pago del Recibo' as keyof MetlifeGMMRaw },
        { header: 'Año Póliza', accessorKey: 'Año de Vida Póliza' as keyof MetlifeGMMRaw },
        { header: 'Estado', accessorKey: 'Estado' as keyof MetlifeGMMRaw },
        {
            header: 'Prima Pagada',
            accessorKey: (row: MetlifeGMMRaw) => {
                const val = row['Prima Pagada'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
        {
            header: 'Comisión Bruto',
            accessorKey: (row: MetlifeGMMRaw) => {
                const val = row['Comisión Bruto'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
        {
            header: 'Comisión Neta',
            accessorKey: (row: MetlifeGMMRaw) => {
                const val = row['Comisión Neta'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
        {
            header: 'IVA Causado',
            accessorKey: (row: MetlifeGMMRaw) => {
                const val = row['IVA Causado'];
                if (val === undefined || val === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(val as number);
            }
        },
    ];

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex items-center justify-between border-b pb-2 flex-none">
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

            <div className="flex-1 min-h-0 overflow-hidden">
                {activeTab === 'VIDA' ? (
                    <DataTable data={vidaData} columns={vidaColumns} className="h-full overflow-auto" />
                ) : (
                    <DataTable data={gmmData} columns={gmmColumns} className="h-full overflow-auto" />
                )}
            </div>
        </div>
    );
}
