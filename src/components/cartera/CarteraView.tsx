'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { DataTable } from '@/components/ui/DataTable';
import { CarteraMetlifeVida, CarteraMetlifeGMM, CarteraSura } from '@/lib/types/cartera';
import clsx from 'clsx';

interface CarteraViewProps {
    data: (CarteraMetlifeVida | CarteraMetlifeGMM | CarteraSura)[];
    insurer: string;
    type: string;
}

export function CarteraView({ data, insurer, type }: CarteraViewProps) {
    const router = useRouter();
    const searchParams = useSearchParams();

    const handleInsurerChange = (newInsurer: string) => {
        const params = new URLSearchParams(searchParams.toString());
        params.set('insurer', newInsurer);
        // Reset type to default for the new insurer
        if (newInsurer === 'Metlife') {
            params.set('type', 'VIDA');
        } else {
            params.delete('type');
        }
        router.push(`/cartera?${params.toString()}`);
    };

    const handleTypeChange = (newType: string) => {
        const params = new URLSearchParams(searchParams.toString());
        params.set('type', newType);
        router.push(`/cartera?${params.toString()}`);
    };

    const formatPercentage = (value: any) => {
        if (typeof value === 'number') {
            return `${(value * 100).toFixed(0)}%`;
        }
        return value;
    };

    const getColumns = () => {
        if (insurer === 'Metlife') {
            if (type === 'VIDA') {
                return [
                    { header: 'Póliza', accessorKey: 'Poliza' },
                    { header: 'Contratante', accessorKey: 'Contratante' },
                    { header: 'Prospectador', accessorKey: 'PROSPECTADOR ' },
                    {
                        header: 'Porcentaje',
                        accessorKey: 'PORCENTAJE ',
                        cell: (info: any) => formatPercentage(info.getValue())
                    },
                ];
            } else { // GMM
                return [
                    { header: 'Póliza', accessorKey: 'POLIZA ' },
                    { header: 'Póliza Actual', accessorKey: 'Poliza actual' },
                    { header: 'Contratante', accessorKey: 'Contratante' },
                    { header: 'Prospectador', accessorKey: 'PROSPECTADOR ' },
                    {
                        header: 'Porcentaje',
                        accessorKey: 'PORCENTAJE',
                        cell: (info: any) => formatPercentage(info.getValue())
                    },
                ];
            }
        } else if (insurer === 'SURA') {
            return [
                { header: 'Póliza', accessorKey: 'PÓLIZA' },
                { header: 'Prospectador', accessorKey: 'PROSPECTADOR' },
                {
                    header: 'Porcentaje',
                    accessorKey: 'PORCENTAJE',
                    cell: (info: any) => formatPercentage(info.getValue())
                },
            ];
        }
        return [];
    };

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex space-x-4 border-b border-gray-200 pb-2">
                {['Metlife', 'SURA', 'Axa', 'AARCO'].map((ins) => (
                    <button
                        key={ins}
                        onClick={() => handleInsurerChange(ins)}
                        className={clsx(
                            'px-4 py-2 text-sm font-medium rounded-md transition-colors',
                            insurer === ins
                                ? 'bg-blue-100 text-blue-700'
                                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                        )}
                    >
                        {ins}
                    </button>
                ))}
            </div>

            {insurer === 'Metlife' && (
                <div className="flex space-x-2">
                    {['VIDA', 'GMM'].map((t) => (
                        <button
                            key={t}
                            onClick={() => handleTypeChange(t)}
                            className={clsx(
                                'px-3 py-1 text-xs font-medium rounded-full border transition-colors',
                                type === t
                                    ? 'bg-blue-600 text-white border-blue-600'
                                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                            )}
                        >
                            {t}
                        </button>
                    ))}
                </div>
            )}

            <div className="flex-1 min-h-0 overflow-hidden bg-white rounded-lg shadow">
                {data.length > 0 ? (
                    <DataTable
                        data={data}
                        columns={getColumns()}
                    />
                ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                        No hay datos disponibles para {insurer} {type ? `- ${type}` : ''}
                    </div>
                )}
            </div>
        </div>
    );
}
