'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ArrowUp, ArrowDown, ArrowUpDown, Check, ChevronDown, Search, X } from 'lucide-react';

interface Column<T> {
    header: string;
    accessorKey: keyof T | ((row: T) => React.ReactNode);
    className?: string;
    enableSorting?: boolean;
    enableFiltering?: boolean;
}

interface DataTableProps<T> {
    data: T[];
    columns: Column<T>[];
    className?: string;
    onRowClick?: (row: T) => void;
    onProcessedDataChange?: (rows: T[]) => void;
    filterMode?: 'text' | 'multi-select';
}

type SortDirection = 'asc' | 'desc' | null;

interface SortConfig<T> {
    key: keyof T | null;
    direction: SortDirection;
}

function columnKey<T>(column: Column<T>): string {
    return typeof column.accessorKey !== 'function' ? String(column.accessorKey) : column.header;
}

function columnValue<T>(column: Column<T>, row: T): string {
    const value = typeof column.accessorKey === 'function'
        ? column.accessorKey(row)
        : row[column.accessorKey];
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

export function DataTable<T>({ data, columns, className, onRowClick, onProcessedDataChange, filterMode = 'text' }: DataTableProps<T>) {
    const [sortConfig, setSortConfig] = useState<SortConfig<T>>({ key: null, direction: null });
    const [filters, setFilters] = useState<Record<string, string>>({});
    const [multiFilters, setMultiFilters] = useState<Record<string, string[]>>({});

    const handleSort = (key: keyof T) => {
        let direction: SortDirection = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        } else if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = null;
        }
        setSortConfig({ key: direction ? key : null, direction });
    };

    const handleFilterChange = (key: string, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
    };

    const filterOptions = useMemo(() => Object.fromEntries(columns.map((column) => {
        const values = Array.from(new Set(data.map((row) => columnValue(column, row)).filter(Boolean)));
        values.sort((left, right) => left.localeCompare(right, 'es-MX', { numeric: true, sensitivity: 'base' }));
        return [columnKey(column), values];
    })), [columns, data]);

    const toggleMultiFilter = (key: string, value: string) => {
        setMultiFilters((current) => {
            const selected = current[key] || [];
            const next = selected.includes(value)
                ? selected.filter((item) => item !== value)
                : [...selected, value];
            return { ...current, [key]: next };
        });
    };

    const processedData = useMemo(() => {
        let filtered = [...data];

        Object.keys(filters).forEach(key => {
            const filterValue = filters[key].toLowerCase();
            if (!filterValue) return;

            filtered = filtered.filter(row => {
                const col = columns.find(c => {
                    // Try to match column by header if accessor is function, or by accessor key
                    if (typeof c.accessorKey !== 'function') {
                        return String(c.accessorKey) === key;
                    }
                    // For function accessors, we use the header as the key for filtering state
                    return c.header === key;
                });

                if (!col) return true;

                const cellValue = columnValue(col, row);
                return cellValue.toLowerCase().includes(filterValue);
            });
        });

        Object.entries(multiFilters).forEach(([key, selected]) => {
            if (!selected.length) return;
            const column = columns.find((candidate) => columnKey(candidate) === key);
            if (!column) return;
            filtered = filtered.filter((row) => selected.includes(columnValue(column, row)));
        });

        // Apply sorting
        if (sortConfig.key && sortConfig.direction) {
            filtered.sort((a, b) => {
                // We only support sorting on direct keys for now to keep it simple
                // or we need a way to resolve the value for sorting
                const aValue = a[sortConfig.key!];
                const bValue = b[sortConfig.key!];

                if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
                if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
                return 0;
            });
        }

        return filtered;
    }, [data, filters, multiFilters, sortConfig, columns]);

    useEffect(() => {
        onProcessedDataChange?.(processedData);
    }, [onProcessedDataChange, processedData]);

    return (
        <div className={twMerge("overflow-x-auto rounded-lg border border-gray-200 shadow-sm", className)}>
            <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
                <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                    <tr>
                        {columns.map((col, idx) => {
                            const isSortable = typeof col.accessorKey !== 'function'; // Only sort direct keys for now
                            const filterKey = columnKey(col);

                            return (
                                <th
                                    key={idx}
                                    className={twMerge("px-4 py-3 text-left font-medium text-gray-900 bg-gray-50 align-top", col.className)}
                                >
                                    <div className="flex flex-col gap-2">
                                        <div
                                            className={clsx("flex items-center gap-1", isSortable && "cursor-pointer select-none hover:text-blue-600")}
                                            onClick={() => isSortable && handleSort(col.accessorKey as keyof T)}
                                        >
                                            {col.header}
                                            {isSortable && (
                                                <span className="text-gray-400">
                                                    {sortConfig.key === col.accessorKey ? (
                                                        sortConfig.direction === 'asc' ? <ArrowUp size={14} className="text-blue-600" /> : <ArrowDown size={14} className="text-blue-600" />
                                                    ) : (
                                                        <ArrowUpDown size={14} />
                                                    )}
                                                </span>
                                            )}
                                        </div>
                                        {filterMode === 'multi-select' ? (
                                            <MultiSelectFilter
                                                label={col.header}
                                                options={filterOptions[filterKey] || []}
                                                selected={multiFilters[filterKey] || []}
                                                onToggle={(value) => toggleMultiFilter(filterKey, value)}
                                                onClear={() => setMultiFilters((current) => ({ ...current, [filterKey]: [] }))}
                                            />
                                        ) : (
                                            <input
                                                type="text"
                                                placeholder="Filtrar..."
                                                className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-normal focus:border-blue-500 focus:outline-none"
                                                value={filters[filterKey] || ''}
                                                onChange={(e) => handleFilterChange(filterKey, e.target.value)}
                                                onClick={(e) => e.stopPropagation()}
                                            />
                                        )}
                                    </div>
                                </th>
                            );
                        })}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                    {processedData.length === 0 ? (
                        <tr>
                            <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                                No hay datos disponibles
                            </td>
                        </tr>
                    ) : (
                        processedData.map((row, rowIdx) => (
                            <tr
                                key={rowIdx}
                                className={clsx(
                                    "hover:bg-gray-50 transition-colors",
                                    onRowClick && "cursor-pointer hover:bg-blue-50"
                                )}
                                onClick={() => onRowClick && onRowClick(row)}
                            >
                                {columns.map((col, colIdx) => (
                                    <td key={colIdx} className="px-4 py-2 text-gray-700 whitespace-nowrap">
                                        {typeof col.accessorKey === 'function'
                                            ? col.accessorKey(row)
                                            : (row[col.accessorKey] as React.ReactNode)}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

function MultiSelectFilter({
    label,
    options,
    selected,
    onToggle,
    onClear,
}: {
    label: string;
    options: string[];
    selected: string[];
    onToggle: (value: string) => void;
    onClear: () => void;
}) {
    const [search, setSearch] = useState('');
    const visibleOptions = options.filter((option) => option.toLocaleLowerCase('es-MX').includes(search.toLocaleLowerCase('es-MX')));
    return (
        <details className="group/filter relative font-normal" onClick={(event) => event.stopPropagation()}>
            <summary className={clsx(
                'flex min-w-32 cursor-pointer list-none items-center justify-between gap-2 rounded border px-2 py-1 text-xs',
                selected.length ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-300 bg-white text-gray-500',
            )}>
                <span className="truncate">{selected.length ? `${selected.length} seleccionados` : 'Seleccionar valores'}</span>
                <ChevronDown className="h-3.5 w-3.5 transition-transform group-open/filter:rotate-180" />
            </summary>
            <div className="absolute left-0 top-full z-30 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-3 shadow-xl">
                <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="truncate text-xs font-semibold text-slate-700">Filtrar {label}</p>
                    {!!selected.length && <button type="button" onClick={onClear} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"><X className="h-3 w-3" /> Limpiar</button>}
                </div>
                <div className="relative mb-2">
                    <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-slate-400" />
                    <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar valor..." className="w-full rounded border border-slate-300 py-1.5 pl-7 pr-2 text-xs text-slate-800 outline-none focus:border-blue-500" />
                </div>
                <div className="max-h-56 space-y-0.5 overflow-y-auto overscroll-contain">
                    {visibleOptions.map((option) => {
                        const checked = selected.includes(option);
                        return <button key={option} type="button" onClick={() => onToggle(option)} className={clsx('flex w-full items-start gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-blue-50', checked && 'bg-blue-50 text-blue-800')}><span className={clsx('mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border', checked ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 bg-white')}>{checked && <Check className="h-3 w-3" />}</span><span className="break-words">{option}</span></button>;
                    })}
                    {!visibleOptions.length && <p className="px-2 py-4 text-center text-xs text-slate-400">Sin coincidencias</p>}
                </div>
            </div>
        </details>
    );
}
