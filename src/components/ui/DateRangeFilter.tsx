'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';

export function DateRangeFilter() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const [startDate, setStartDate] = useState(searchParams.get('startDate') || '');
    const [endDate, setEndDate] = useState(searchParams.get('endDate') || '');

    // Update local state if URL params change externally
    useEffect(() => {
        setStartDate(searchParams.get('startDate') || '');
        setEndDate(searchParams.get('endDate') || '');
    }, [searchParams]);

    const handleApply = () => {
        const params = new URLSearchParams(searchParams.toString());

        if (startDate) {
            params.set('startDate', startDate);
        } else {
            params.delete('startDate');
        }

        if (endDate) {
            params.set('endDate', endDate);
        } else {
            params.delete('endDate');
        }

        router.push(`?${params.toString()}`);
    };

    const handleClear = () => {
        setStartDate('');
        setEndDate('');
        const params = new URLSearchParams(searchParams.toString());
        params.delete('startDate');
        params.delete('endDate');
        router.push(`?${params.toString()}`);
    };

    return (
        <div className="flex flex-col sm:flex-row items-end gap-4 bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
            <div>
                <label htmlFor="startDate" className="block text-sm font-medium text-gray-700 mb-1">
                    Fecha Inicio
                </label>
                <input
                    type="date"
                    id="startDate"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                />
            </div>
            <div>
                <label htmlFor="endDate" className="block text-sm font-medium text-gray-700 mb-1">
                    Fecha Fin
                </label>
                <input
                    type="date"
                    id="endDate"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                />
            </div>
            <div className="flex gap-2">
                <button
                    onClick={handleApply}
                    className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                    Filtrar
                </button>
                {(startDate || endDate) && (
                    <button
                        onClick={handleClear}
                        className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                    >
                        Limpiar
                    </button>
                )}
            </div>
        </div>
    );
}
