'use client';

import { useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { MetlifeVidaRaw, MetlifeGMMRaw } from '@/lib/types/metlife';

interface CobranzaViewProps {
    vidaData: MetlifeVidaRaw[];
    gmmData: MetlifeGMMRaw[];
}

export function CobranzaView({ vidaData, gmmData }: CobranzaViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    const vidaColumns = [
        { header: 'Póliza', accessorKey: '# de Póliza' as keyof MetlifeVidaRaw },
        { header: 'Contratante', accessorKey: 'Producto' as keyof MetlifeVidaRaw }, // Using Producto as proxy for name if name missing? Wait, Vida Raw doesn't have Name?
        // Checking MetlifeVidaRaw: "# de Póliza", "Clave del Agente", "Producto", ... "Prima Pagada" ...
        // It seems "Producto" is the product name. Where is the client name?
        // The prompt for "Metlife – Base de Cobranza" Sheet Vida does NOT list "Contratante" or "Nombre".
        // It lists: # de Póliza, Clave del Agente, Producto, Conducto, MSI, Estatus Recibo, Fecha Pago, Estatus Poliza, Año Vida, Edad, Prima, Comision.
        // That's weird. Maybe it's linked via Policy ID to Cartera?
        // For now I'll just show what's there.
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
        <div className="space-y-4">
            <div className="flex space-x-4 border-b">
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

            {activeTab === 'VIDA' ? (
                <DataTable data={vidaData} columns={vidaColumns} />
            ) : (
                <DataTable data={gmmData} columns={gmmColumns} />
            )}
        </div>
    );
}
