'use client';

import { useState } from 'react';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { CobranzaMetlifeBase, CobranzaSura, CobranzaAarco } from '@/lib/types/cobranza';
import { exportToExcel } from '@/lib/utils/export';

interface CobranzaViewProps {
    vidaData?: CobranzaMetlifeBase[];
    gmmData?: CobranzaMetlifeBase[];
    suraData?: CobranzaSura[];
    aarcoData?: CobranzaAarco[];
    insurer?: string;
}

export function CobranzaView({ vidaData = [], gmmData = [], suraData = [], aarcoData = [], insurer = 'Metlife' }: CobranzaViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    const handleExport = () => {
        let data: (CobranzaMetlifeBase | CobranzaSura | CobranzaAarco)[] = [];
        let prefix = '';

        if (insurer === 'Metlife') {
            data = activeTab === 'VIDA' ? vidaData : gmmData.map(row =>
                Object.fromEntries(Object.entries(row).filter(([key]) => key !== 'Pagado Hasta'))
            ) as CobranzaMetlifeBase[];
            prefix = `Cobranza_Metlife_${activeTab}`;
        } else if (insurer === 'SURA') {
            data = suraData;
            prefix = `Cobranza_SURA`;
        } else if (insurer === 'AARCO_AXA') {
            data = aarcoData;
            prefix = `Cobranza_AARCO_AXA`;
        }

        const fileName = `${prefix}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    const baseColumns: Column<CobranzaMetlifeBase>[] = [
        ...(['# de Póliza', 'Contratante', 'Producto', 'Pagado Hasta', 'Estado',
            'Inicio Vigencia', 'Fin Vigencia', 'Forma de Pago', 'Conducto de Cobro', 'Moneda'] as const)
            .map(key => ({ header: key, accessorKey: key })),
        ...(['Prima Anual', 'Prima Modal'] as const).map(key => ({
            header: key,
            accessorKey: key,
            cell: (row: CobranzaMetlifeBase) => row[key] == null ? '—' :
                new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(row[key]),
        })),
        ...(['Clave Agente', 'Agente', 'Promotoría', 'RFC'] as const)
            .map(key => ({ header: key, accessorKey: key })),
    ];
    const vidaColumns = baseColumns;
    const gmmColumns: Column<CobranzaMetlifeBase>[] = baseColumns
        .filter(column => column.accessorKey !== 'Prima Modal')
        .flatMap(column => column.accessorKey === 'Pagado Hasta' ? [
            { header: 'Pagado Hasta (base)', accessorKey: 'Pagado Hasta (base)' },
            { header: 'Pagado Hasta (portal)', accessorKey: 'Pagado Hasta (portal)' },
            { header: 'Última consulta al portal (UTC)', accessorKey: 'Última consulta al portal' },
        ] : [column]);

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

    const aarcoColumns = [
        { header: 'CIA', accessorKey: 'CIA' as keyof CobranzaAarco },
        { header: 'Póliza', accessorKey: 'NUM_POL' as keyof CobranzaAarco },
        { header: 'Cliente', accessorKey: 'CLIENTE' as keyof CobranzaAarco },
        { header: 'Prospectador', accessorKey: 'PROSPECTADOR' as keyof CobranzaAarco },
        { header: 'Fecha Cobro', accessorKey: 'F_COBRO' as keyof CobranzaAarco },
        {
            header: 'Prima Neta',
            accessorKey: (row: CobranzaAarco) => {
                if (row['PRIMA_NETA_MN'] === undefined || row['PRIMA_NETA_MN'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['PRIMA_NETA_MN']);
            }
        },
        {
            header: 'Comisión Apli.',
            accessorKey: (row: CobranzaAarco) => {
                if (row['COM_APL_MN'] === undefined || row['COM_APL_MN'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['COM_APL_MN']);
            }
        },
        {
            header: '% Com. Prosp.',
            accessorKey: (row: CobranzaAarco) => {
                if (row['% COMISION PROSPECTADOR'] === undefined || row['% COMISION PROSPECTADOR'] === null) return '-';
                return row['% COMISION PROSPECTADOR']; // Assuming it's already a percentage number or we can format if needed. User just said money format for others.
            }
        },
        {
            header: '$ Com. Prosp.',
            accessorKey: (row: CobranzaAarco) => {
                if (row['$ COMISION PROSPECTADOR'] === undefined || row['$ COMISION PROSPECTADOR'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['$ COMISION PROSPECTADOR']);
            }
        },
    ];

    return (
        <div className="flex flex-col h-full space-y-4">
            {insurer === 'Metlife' && (
                <p className="text-sm text-white/80">
                    Bases de Vida y GMM actualizadas desde Carga de Bases. El rango filtra por Pagado Hasta de la base. En GMM, la fecha del portal corresponde a la última consulta; queda vacía si no hay un resultado válido.
                </p>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-2 flex-none">
                <div className="flex min-w-0 space-x-2 sm:space-x-4">
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
                    {insurer === 'AARCO_AXA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-white text-white">
                            AARCO & AXA Cobranza
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
                ) : insurer === 'SURA' ? (
                    <DataTable data={suraData} columns={suraColumns} className="h-full overflow-auto" />
                ) : (
                    <DataTable data={aarcoData} columns={aarcoColumns} className="h-full overflow-auto" />
                )}
            </div>
        </div>
    );
}
