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

    const vidaColumns = [
        { header: 'Póliza', accessorKey: '# de Póliza' as keyof MetlifeVidaRaw },
        { header: 'Producto', accessorKey: 'Producto' as keyof MetlifeVidaRaw },
        { header: 'Estatus Recibo', accessorKey: 'Estatus Recibo' as keyof MetlifeVidaRaw },
        { header: 'Prima Pagada', accessorKey: 'Prima Pagada' as keyof MetlifeVidaRaw },
        { header: 'Comisión Neta', accessorKey: 'Comisión Neta' as keyof MetlifeVidaRaw },
    ];

    const gmmColumns = [
        { header: 'Póliza', accessorKey: '# de Póliza' as keyof MetlifeGMMRaw },
        { header: 'Producto', accessorKey: 'Producto' as keyof MetlifeGMMRaw },
        { header: 'Estatus Recibo', accessorKey: 'Estatus Recibo' as keyof MetlifeGMMRaw },
        { header: 'Prima Pagada', accessorKey: 'Prima Pagada' as keyof MetlifeGMMRaw },
        { header: 'Comisión Neta', accessorKey: 'Comisión Neta' as keyof MetlifeGMMRaw },
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
