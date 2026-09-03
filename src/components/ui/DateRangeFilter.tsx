'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';
import { getDefaultDateRange } from '@/lib/dateRange';

interface DateRangeFilterProps {
    initialStartDate?: string;
    initialEndDate?: string;
    startLabel?: string;
    endLabel?: string;
    initializeUrl?: boolean;
    onApply?: (startDate: string, endDate: string) => Promise<void> | void;
}

export function DateRangeFilter({
    initialStartDate,
    initialEndDate,
    startLabel = 'Fecha Inicio',
    endLabel = 'Fecha Fin',
    initializeUrl = true,
    onApply,
}: DateRangeFilterProps = {}) {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const [isNavigationPending, startTransition] = useTransition();
    const [isApplyPending, setIsApplyPending] = useState(false);

    const defaults = getDefaultDateRange();

    // Initialize state from URL or defaults
    const [startDate, setStartDate] = useState(initialStartDate || searchParams.get('startDate') || defaults.start);
    const [endDate, setEndDate] = useState(initialEndDate || searchParams.get('endDate') || defaults.end);
    const hasInvalidRange = Boolean(startDate && endDate && startDate > endDate);
    const isPending = isNavigationPending || isApplyPending;

    useEffect(() => {
        if (!initializeUrl || searchParams.has('startDate') || searchParams.has('endDate')) return;

        const params = new URLSearchParams(searchParams.toString());
        params.set('startDate', defaults.start);
        params.set('endDate', defaults.end);
        router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    }, [defaults.end, defaults.start, initializeUrl, pathname, router, searchParams]);

    const navigateWithDates = async (nextStartDate: string, nextEndDate: string) => {
        const params = new URLSearchParams(searchParams.toString());
        params.set('startDate', nextStartDate);
        params.set('endDate', nextEndDate);
        const url = `${pathname}?${params.toString()}`;

        if (onApply) {
            window.history.replaceState(window.history.state, '', url);
            setIsApplyPending(true);
            try {
                await onApply(nextStartDate, nextEndDate);
            } finally {
                setIsApplyPending(false);
            }
            return;
        }

        startTransition(() => {
            router.replace(url, { scroll: false });
        });
    };

    const handleApply = () => void navigateWithDates(startDate, endDate);

    const handleClear = () => {
        // Reset to defaults instead of empty
        const defs = getDefaultDateRange();
        setStartDate(defs.start);
        setEndDate(defs.end);
        void navigateWithDates(defs.start, defs.end);
    };

    return (
        <div
            className="flex flex-col sm:flex-row items-stretch sm:items-end gap-4 bg-white p-4 rounded-lg border border-gray-200 shadow-sm"
        >
            <div className="min-w-0 flex-1 sm:flex-none">
                <label htmlFor="startDate" className="block text-sm font-medium text-gray-700 mb-1">
                    {startLabel}
                </label>
                <input
                    type="date"
                    id="startDate"
                    name="startDate"
                    value={startDate}
                    max={endDate || undefined}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border text-gray-900"
                />
            </div>
            <div className="min-w-0 flex-1 sm:flex-none">
                <label htmlFor="endDate" className="block text-sm font-medium text-gray-700 mb-1">
                    {endLabel}
                </label>
                <input
                    type="date"
                    id="endDate"
                    name="endDate"
                    value={endDate}
                    min={startDate || undefined}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border text-gray-900"
                />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex">
                <button
                    type="button"
                    onClick={handleApply}
                    disabled={isPending || !startDate || !endDate || hasInvalidRange}
                    className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
                >
                    {isPending ? 'Actualizando...' : 'Filtrar'}
                </button>
                <button
                    type="button"
                    onClick={handleClear}
                    disabled={isPending}
                    className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
                >
                    Restablecer
                </button>
            </div>
            {hasInvalidRange && (
                <p className="self-center text-sm font-medium text-red-600" role="alert">
                    La fecha inicial no puede ser posterior a la fecha final.
                </p>
            )}
        </div>
    );
}
