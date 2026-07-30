'use client';

import { useMemo, useState } from 'react';
import { CakeSlice, Download, Search, ShieldAlert } from 'lucide-react';

import { BirthdayDirectory } from '@/lib/types/cumpleanos';

type ColumnFilters = {
    client: string;
    rfc: string;
    policies: string;
    birthDate: string;
    nextBirthday: string;
    agent: string;
    promotoria: string;
};

const EMPTY_FILTERS: ColumnFilters = {
    client: '',
    rfc: '',
    policies: '',
    birthDate: '',
    nextBirthday: '',
    agent: '',
    promotoria: '',
};

const dateFormatter = new Intl.DateTimeFormat('es-MX', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
});

function displayDate(value: string) {
    return dateFormatter.format(new Date(`${value}T00:00:00Z`));
}

function normalize(value: string | number) {
    return String(value).trim().toLocaleLowerCase('es-MX');
}

function includesFilter(value: string | number, filter: string) {
    const normalizedFilter = normalize(filter);
    return !normalizedFilter || normalize(value).includes(normalizedFilter);
}

export function CumpleanosView({ directory }: { directory: BirthdayDirectory }) {
    const [query, setQuery] = useState('');
    const [filters, setFilters] = useState<ColumnFilters>(EMPTY_FILTERS);
    const normalizedQuery = query.trim().toLocaleLowerCase('es-MX');
    const clients = useMemo(() => {
        return directory.clients.filter((client) => {
            const policyText = client.policies
                .map((policy) => `${policy.branch} ${policy.policy_number}`)
                .join(' ');
            const nextBirthdayText = client.days_until_birthday === 0
                ? 'hoy 0'
                : `en ${client.days_until_birthday} días ${client.days_until_birthday}`;
            const matchesGlobalQuery = !normalizedQuery || [
                client.client_name,
                client.rfc,
                client.agent_label,
                client.promotoria,
                policyText,
            ].some((value) => value.toLocaleLowerCase('es-MX').includes(normalizedQuery));

            return matchesGlobalQuery
                && includesFilter(client.client_name, filters.client)
                && includesFilter(client.rfc, filters.rfc)
                && includesFilter(policyText, filters.policies)
                && (
                    includesFilter(client.birth_date, filters.birthDate)
                    || includesFilter(displayDate(client.birth_date), filters.birthDate)
                )
                && includesFilter(nextBirthdayText, filters.nextBirthday)
                && includesFilter(client.agent_label || 'Agente no identificado', filters.agent)
                && includesFilter(client.promotoria || 'Sin asignar', filters.promotoria);
        });
    }, [directory.clients, filters, normalizedQuery]);

    const updateFilter = (field: keyof ColumnFilters, value: string) => {
        setFilters((current) => ({ ...current, [field]: value }));
    };

    const exportToExcel = async () => {
        const XLSX = await import('xlsx');
        const rows = clients.map((client) => ({
            Cliente: client.client_name,
            RFC: client.rfc,
            Pólizas: client.policies
                .map((policy) => `${policy.branch} · ${policy.policy_number}`)
                .join(', '),
            'Fecha de cumpleaños': displayDate(client.birth_date),
            'Próximo cumpleaños': client.days_until_birthday === 0
                ? 'Hoy'
                : `En ${client.days_until_birthday} días`,
            'RFC Agente': client.agent_rfc,
            Agente: client.agent_name,
            Promotoría: client.promotoria || 'Sin asignar',
        }));
        const worksheet = XLSX.utils.json_to_sheet(rows);
        worksheet['!cols'] = [
            { wch: 34 },
            { wch: 16 },
            { wch: 46 },
            { wch: 24 },
            { wch: 22 },
            { wch: 16 },
            { wch: 38 },
            { wch: 22 },
        ];
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Cumpleaños');
        XLSX.writeFile(workbook, `cumpleanos-clientes-${directory.generated_on}.xlsx`);
    };

    const filterInput = (
        field: keyof ColumnFilters,
        label: string,
    ) => (
        <input
            value={filters[field]}
            onChange={(event) => updateFilter(field, event.target.value)}
            onClick={(event) => event.stopPropagation()}
            placeholder={`Filtrar ${label.toLocaleLowerCase('es-MX')}...`}
            aria-label={`Filtrar por ${label}`}
            className="mt-2 w-full min-w-28 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-normal normal-case tracking-normal text-slate-800 outline-none placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
        />
    );

    return (
        <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="grid flex-none gap-3 border-b border-slate-200 p-5 sm:grid-cols-3">
                <div className="rounded-xl bg-indigo-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Clientes</p>
                    <p className="mt-1 text-2xl font-bold text-slate-900">{directory.summary.total_clients}</p>
                </div>
                <div className="rounded-xl bg-pink-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-pink-600">Este mes</p>
                    <p className="mt-1 text-2xl font-bold text-slate-900">{directory.summary.birthdays_this_month}</p>
                </div>
                <div className="rounded-xl bg-amber-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Próximos 30 días</p>
                    <p className="mt-1 text-2xl font-bold text-slate-900">{directory.summary.birthdays_next_30_days}</p>
                </div>
            </div>

            <div className="flex flex-none flex-col gap-3 border-b border-slate-200 p-5 lg:flex-row lg:items-center">
                <label className="relative block w-full max-w-2xl">
                    <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                    <input
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder="Buscar por cliente, RFC, póliza, agente o promotoría..."
                        className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                    />
                </label>
                <p className="whitespace-nowrap text-sm text-slate-500 lg:ml-auto">
                    {clients.length} de {directory.summary.total_clients} clientes
                </p>
                <button
                    type="button"
                    onClick={exportToExcel}
                    disabled={clients.length === 0}
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-indigo-200 bg-white px-4 py-2.5 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <Download className="h-4 w-4" />
                    Exportar a Excel
                </button>
            </div>

            {directory.summary.unmatched_agent_rows > 0 && (
                <div className="mx-5 mt-4 flex flex-none items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                        {directory.summary.unmatched_agent_rows} pólizas no encontraron una clave definitiva en la base de agentes.
                    </span>
                </div>
            )}

            <div className="min-h-0 flex-1 overflow-auto px-5 pb-5">
                <table className="w-full min-w-[1260px] border-separate border-spacing-0 text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-slate-600">
                        <tr>
                            <th className="sticky top-0 z-30 min-w-52 rounded-l-lg bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Cliente
                                {filterInput('client', 'Cliente')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-44 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                RFC
                                {filterInput('rfc', 'RFC')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-60 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Pólizas
                                {filterInput('policies', 'Pólizas')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-56 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Fecha de cumpleaños
                                {filterInput('birthDate', 'Fecha')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-52 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Próximo cumpleaños
                                {filterInput('nextBirthday', 'Próximo cumpleaños')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-80 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Agente
                                {filterInput('agent', 'Agente')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-44 rounded-r-lg bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Promotoría
                                {filterInput('promotoria', 'Promotoría')}
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {clients.map((client) => (
                            <tr key={client.rfc} className="align-top hover:bg-slate-50">
                                <td className="px-4 py-4 font-semibold text-slate-900">{client.client_name}</td>
                                <td className="whitespace-nowrap px-4 py-4 font-mono text-slate-700">{client.rfc}</td>
                                <td className="px-4 py-4">
                                    <div className="flex max-w-xs flex-wrap gap-1.5">
                                        {client.policies.map((policy) => (
                                            <span
                                                key={`${policy.branch}-${policy.policy_number}`}
                                                className="whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
                                            >
                                                {policy.branch} · {policy.policy_number}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="whitespace-nowrap px-4 py-4 text-slate-700">{displayDate(client.birth_date)}</td>
                                <td className="px-4 py-4">
                                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap font-medium text-pink-700">
                                        <CakeSlice className="h-4 w-4" />
                                        {client.days_until_birthday === 0
                                            ? 'Hoy'
                                            : `En ${client.days_until_birthday} días`}
                                    </span>
                                </td>
                                <td className="min-w-72 px-4 py-4 text-slate-700">
                                    {client.agent_label || 'Agente no identificado'}
                                </td>
                                <td className="whitespace-nowrap px-4 py-4 font-medium text-slate-700">
                                    {client.promotoria || 'Sin asignar'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {clients.length === 0 && (
                    <div className="py-16 text-center text-slate-500">
                        No hay clientes que coincidan con la búsqueda.
                    </div>
                )}
            </div>
        </div>
    );
}
