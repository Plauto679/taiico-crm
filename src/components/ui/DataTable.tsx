import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface Column<T> {
    header: string;
    accessorKey: keyof T | ((row: T) => React.ReactNode);
    className?: string;
}

interface DataTableProps<T> {
    data: T[];
    columns: Column<T>[];
    className?: string;
}

export function DataTable<T>({ data, columns, className }: DataTableProps<T>) {
    return (
        <div className={twMerge("overflow-x-auto rounded-lg border border-gray-200 shadow-sm", className)}>
            <table className="min-w-full divide-y divide-gray-200 bg-white text-sm">
                <thead className="bg-gray-50">
                    <tr>
                        {columns.map((col, idx) => (
                            <th
                                key={idx}
                                className={twMerge("px-4 py-3 text-left font-medium text-gray-900", col.className)}
                            >
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                    {data.length === 0 ? (
                        <tr>
                            <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                                No hay datos disponibles
                            </td>
                        </tr>
                    ) : (
                        data.map((row, rowIdx) => (
                            <tr key={rowIdx} className="hover:bg-gray-50">
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
