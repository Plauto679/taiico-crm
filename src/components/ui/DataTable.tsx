'use client';

import React, { useState, useMemo } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';

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
}

type SortDirection = 'asc' | 'desc' | null;

interface SortConfig<T> {
    key: keyof T | null;
    direction: SortDirection;
}

export function DataTable<T>({ data, columns, className, onRowClick }: DataTableProps<T>) {
    const [sortConfig, setSortConfig] = useState<SortConfig<T>>({ key: null, direction: null });
    const [filters, setFilters] = useState<Record<string, string>>({});

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

    const processedData = useMemo(() => {
        let filtered = [...data];

        // Apply filters
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

                let cellValue = '';
                if (typeof col.accessorKey === 'function') {
                    // This is tricky for ReactNode, we might skip filtering or try to stringify
                    // For now, let's skip complex renderers or assume they return strings/numbers
                    const val = col.accessorKey(row);
                    if (typeof val === 'string' || typeof val === 'number') {
                        cellValue = String(val);
                    }
                } else {
                    cellValue = String(row[col.accessorKey]);
                }

                return cellValue.toLowerCase().includes(filterValue);
            });
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
    }, [data, filters, sortConfig, columns]);

    return (
        <div className={twMerge("overflow-x-auto rounded-lg border border-gray-200 shadow-sm", className)}>
            <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
                <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                    <tr>
                        {columns.map((col, idx) => {
                            const isSortable = typeof col.accessorKey !== 'function'; // Only sort direct keys for now
                            const filterKey = typeof col.accessorKey !== 'function' ? String(col.accessorKey) : col.header;

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
                                        <input
                                            type="text"
                                            placeholder={`Filtrar...`}
                                            className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-normal focus:border-blue-500 focus:outline-none"
                                            value={filters[filterKey] || ''}
                                            onChange={(e) => handleFilterChange(filterKey, e.target.value)}
                                            onClick={(e) => e.stopPropagation()}
                                        />
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
