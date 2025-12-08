'use client';

import { useState } from 'react';
import { DataTable } from '@/components/ui/DataTable';
import { CobranzaGMM, CobranzaVida, CobranzaSura } from '@/lib/types/cobranza';
import { exportToExcel } from '@/lib/utils/export';

interface CobranzaViewProps {
    vidaData?: CobranzaVida[];
    gmmData?: CobranzaGMM[];
    suraData?: CobranzaSura[];
    insurer?: string;
}

export function CobranzaView({ vidaData = [], gmmData = [], suraData = [], insurer = 'Metlife' }: CobranzaViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    const handleExport = () => {
        let data: any[] = [];
        let prefix = '';

        if (insurer === 'Metlife') {
            data = activeTab === 'VIDA' ? vidaData : gmmData;
            prefix = `Cobranza_Metlife_${activeTab}`;
        } else if (insurer === 'SURA') {
            data = suraData;
            prefix = `Cobranza_SURA`;
        }

        const fileName = `${prefix}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    const vidaColumns = [
        { header: '# Póliza', accessorKey: '# de Póliza' as keyof CobranzaVida },
        { header: 'Producto', accessorKey: 'Producto' as keyof CobranzaVida },
        { header: 'Conducto', accessorKey: 'Conducto de Cobro' as keyof CobranzaVida },
        { header: 'Fecha Pago', accessorKey: 'Fecha de Pago del Recibo' as keyof CobranzaVida },
        { header: 'Año Póliza', accessorKey: 'Año de Vida Póliza' as keyof CobranzaVida },
        {
            header: 'Prima Pagada',
            accessorKey: (row: CobranzaVida) => {
                if (row['Prima Pagada'] === undefined || row['Prima Pagada'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Prima Pagada']);
            }
        },
        {
            header: 'Comisión Bruto',
            accessorKey: (row: CobranzaVida) => {
                if (row['Comisión Bruto'] === undefined || row['Comisión Bruto'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Comisión Bruto']);
            }
        },
        {
            header: 'Comisión Neta',
            accessorKey: (row: CobranzaVida) => {
                if (row['Comisión Neta'] === undefined || row['Comisión Neta'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Comisión Neta']);
            }
        },
    ];

    const gmmColumns = [
        { header: '# Póliza', accessorKey: '# de Póliza' as keyof CobranzaGMM },
        { header: 'Producto', accessorKey: 'Producto' as keyof CobranzaGMM },
        { header: 'Conducto', accessorKey: 'Conducto de Cobro' as keyof CobranzaGMM },
        { header: 'Fecha Pago', accessorKey: 'Fecha de Pago del Recibo' as keyof CobranzaGMM },
        { header: 'Año Póliza', accessorKey: 'Año de Vida Póliza' as keyof CobranzaGMM },
        { header: 'Estado', accessorKey: 'Estado' as keyof CobranzaGMM },
        {
            header: 'Prima Pagada',
            accessorKey: (row: CobranzaGMM) => {
                if (row['Prima Pagada'] === undefined || row['Prima Pagada'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Prima Pagada']);
            }
        },
        {
            header: 'Comisión Bruto',
            accessorKey: (row: CobranzaGMM) => {
                if (row['Comisión Bruto'] === undefined || row['Comisión Bruto'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Comisión Bruto']);
            }
        },
        {
            header: 'Comisión Neta',
            accessorKey: (row: CobranzaGMM) => {
                if (row['Comisión Neta'] === undefined || row['Comisión Neta'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Comisión Neta']);
            }
        },
        {
            header: 'IVA Causado',
            accessorKey: (row: CobranzaGMM) => {
                if (row['IVA Causado'] === undefined || row['IVA Causado'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['IVA Causado']);
            }
        },
    ];

    // 'Póliza', 'Contratante', 'Ramo', 'Prima Total', 'Prima Neta', '% Comisión pagado', 'Monto Comisión Neta', 'Total Comisión pagado' & 'Fecha aplicación de la póliza'
    const suraColumns = [
        { header: 'Póliza', accessorKey: 'Póliza' as keyof CobranzaSura },
        { header: 'Contratante', accessorKey: 'Contratante' as keyof CobranzaSura },
        { header: 'Ramo', accessorKey: 'Ramo' as keyof CobranzaSura },
        {
            header: 'Prima Total',
            accessorKey: (row: CobranzaSura) => {
                if (row['Prima Total'] === undefined || row['Prima Total'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Prima Total']);
            }
        },
        {
            header: 'Prima Neta',
            accessorKey: (row: CobranzaSura) => {
                if (row['Prima Neta'] === undefined || row['Prima Neta'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Prima Neta']);
            }
        },
        {
            header: '% Comisión',
            accessorKey: (row: CobranzaSura) => {
                if (row['% Comisión pagado'] === undefined || row['% Comisión pagado'] === null) return '-';
                return `${(row['% Comisión pagado'] * 100).toFixed(2)}%`;
            }
        },
        {
            header: 'Monto Comisión',
            accessorKey: (row: CobranzaSura) => {
                if (row['Monto Comisión Neta'] === undefined || row['Monto Comisión Neta'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Monto Comisión Neta']);
            }
        },
        {
            header: 'Total Comisión',
            accessorKey: (row: CobranzaSura) => {
                if (row['Total Comisión pagado'] === undefined || row['Total Comisión pagado'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['Total Comisión pagado']);
            }
        },
        { header: 'Fecha Aplicación', accessorKey: 'Fecha aplicación de la póliza' as keyof CobranzaSura },
    ];

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex items-center justify-between border-b pb-2 flex-none">
                <div className="flex space-x-4">
                    {insurer === 'Metlife' && (
                        <>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'VIDA' ? 'border-b-2 border-white text-white' : 'text-white/70 hover:text-white'}`}
                                onClick={() => setActiveTab('VIDA')}
                            >
                                Vida
                            </button>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'GMM' ? 'border-b-2 border-white text-white' : 'text-white/70 hover:text-white'}`}
                                onClick={() => setActiveTab('GMM')}
                            >
                                GMM
                            </button>
                        </>
                    )}
                    {insurer === 'SURA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-white text-white">
                            SURA Cobranza
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
                        <DataTable data={vidaData} columns={vidaColumns} className="h-full overflow-auto" />
                    ) : (
                        <DataTable data={gmmData} columns={gmmColumns} className="h-full overflow-auto" />
                    )
                ) : (
                    <DataTable data={suraData} columns={suraColumns} className="h-full overflow-auto" />
                )}
            </div>
        </div>
    );
}
