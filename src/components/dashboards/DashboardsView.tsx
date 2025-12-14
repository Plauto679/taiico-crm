'use client';

import { useState, useMemo } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { CobranzaGMM, CobranzaVida, CobranzaSura, CobranzaAarco } from '@/lib/types/cobranza';

interface DashboardsViewProps {
    vidaData?: CobranzaVida[];
    gmmData?: CobranzaGMM[];
    suraData?: CobranzaSura[];
    aarcoData?: CobranzaAarco[];
    insurer?: string;
}

export function DashboardsView({ vidaData = [], gmmData = [], suraData = [], aarcoData = [], insurer = 'Metlife' }: DashboardsViewProps) {
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');

    // Helper to format money for tooltip
    const formatMoney = (value: number) => {
        return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(value);
    };

    const chartData = useMemo(() => {
        const dataMap = new Map<string, number>();

        // Select Data Source and Metric Key based on rules
        let sourceData: any[] = [];
        let dateKey = '';
        let valueKey = '';

        if (insurer === 'Metlife') {
            if (activeTab === 'VIDA') {
                sourceData = vidaData;
                dateKey = 'Fecha de Pago del Recibo';
                valueKey = 'Comisión Neta';
            } else { // GMM
                sourceData = gmmData;
                dateKey = 'Fecha de Pago del Recibo';
                valueKey = 'Comisión Neta';
            }
        } else if (insurer === 'SURA') {
            sourceData = suraData;
            dateKey = 'Fecha aplicación de la póliza';
            valueKey = 'Total Comisión pagado';
        } else if (insurer === 'AARCO_AXA') {
            sourceData = aarcoData;
            dateKey = 'F_COBRO';
            valueKey = 'COM_APL_MN';
        }

        // Aggregate by Month
        sourceData.forEach(item => {
            const dateStr = item[dateKey];
            const val = item[valueKey];

            if (dateStr && typeof val === 'number') {
                // Extract YYYY-MM
                const date = new Date(dateStr);
                if (!isNaN(date.getTime())) {
                    const monthKey = date.toISOString().slice(0, 7); // YYYY-MM
                    const current = dataMap.get(monthKey) || 0;
                    dataMap.set(monthKey, current + val);
                }
            }
        });

        // Convert Map to Array and Sort
        const result = Array.from(dataMap.entries()).map(([month, total]) => ({
            month,
            total
        }));

        return result.sort((a, b) => a.month.localeCompare(b.month)); // Sort chronological

    }, [vidaData, gmmData, suraData, aarcoData, insurer, activeTab]);

    return (
        <div className="flex flex-col h-full space-y-6">

            {/* Tab Selection for Metlife */}
            {insurer === 'Metlife' && (
                <div className="flex space-x-2">
                    <button
                        className={`px-4 py-2 font-medium rounded-md transition-colors ${activeTab === 'VIDA' ? 'bg-blue-600 text-white shadow' : 'bg-white text-gray-600 hover:bg-gray-100 border'}`}
                        onClick={() => setActiveTab('VIDA')}
                    >
                        Vida
                    </button>
                    <button
                        className={`px-4 py-2 font-medium rounded-md transition-colors ${activeTab === 'GMM' ? 'bg-blue-600 text-white shadow' : 'bg-white text-gray-600 hover:bg-gray-100 border'}`}
                        onClick={() => setActiveTab('GMM')}
                    >
                        GMM
                    </button>
                </div>
            )}

            {/* Chart Container */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex-1 min-h-[400px]">
                <h2 className="text-lg font-semibold text-gray-800 mb-6">
                    {insurer} - {insurer === 'Metlife' ? activeTab : 'Comisiones'}
                </h2>

                {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="90%">
                        <BarChart
                            data={chartData}
                            margin={{
                                top: 20,
                                right: 30,
                                left: 20,
                                bottom: 5,
                            }}
                        >
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis
                                dataKey="month"
                                tickFormatter={(val) => val}
                            />
                            <YAxis
                                tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`} // Format as K for space
                            />
                            <Tooltip
                                formatter={(value: number) => [formatMoney(value), 'Total']}
                                labelFormatter={(label) => `Mes: ${label}`}
                            />
                            <Legend />
                            <Bar dataKey="total" name="Comisión Total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex h-full items-center justify-center text-gray-500">
                        No hay datos para mostrar en este periodo.
                    </div>
                )}
            </div>
        </div>
    );
}
