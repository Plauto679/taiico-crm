'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';

export function DateRangeFilter() {
    const router = useRouter();
    const searchParams = useSearchParams();

    // Helper to get default dates
    const getDefaults = () => {
        const today = new Date();
        const start = new Date(today);
        start.setMonth(today.getMonth() - 1);
        const end = new Date(today);
        end.setMonth(today.getMonth() + 1);
        return {
            start: start.toISOString().split('T')[0],
            end: end.toISOString().split('T')[0]
        };
    };

    const defaults = getDefaults();

    // Initialize state from URL or defaults
    const [startDate, setStartDate] = useState(searchParams.get('startDate') || defaults.start);
    const [endDate, setEndDate] = useState(searchParams.get('endDate') || defaults.end);

    // Effect to update URL with defaults on mount if missing
    useEffect(() => {
        const currentStart = searchParams.get('startDate');
        const currentEnd = searchParams.get('endDate');

        if (!currentStart && !currentEnd) {
            const params = new URLSearchParams(searchParams.toString());
            params.set('startDate', defaults.start);
            params.set('endDate', defaults.end);
            router.replace(`?${params.toString()}`);
        } else {
            // Sync state if URL changes
            setStartDate(currentStart || defaults.start);
            setEndDate(currentEnd || defaults.end);
        }
    }, [searchParams, router, defaults.start, defaults.end]);

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
        // Reset to defaults instead of empty
        const defs = getDefaults();
        setStartDate(defs.start);
        setEndDate(defs.end);
        const params = new URLSearchParams(searchParams.toString());
        params.set('startDate', defs.start);
        params.set('endDate', defs.end);
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
                <button
                    onClick={handleClear}
                    className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                >
                    Restablecer
                </button>
            </div>
        </div>
    );
}
