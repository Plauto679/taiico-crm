'use client';

import { useMemo, useState } from 'react';
import { CakeSlice, Download, Search, ShieldAlert } from 'lucide-react';

import { AgentBirthdayDirectory } from '@/lib/types/cumpleanosAgentes';

type ColumnFilters = {
    agent: string;
    rfc: string;
    keys: string;
    birthDate: string;
    nextBirthday: string;
    promotoria: string;
    email: string;
    status: string;
};

const EMPTY_FILTERS: ColumnFilters = {
    agent: '',
    rfc: '',
    keys: '',
    birthDate: '',
    nextBirthday: '',
    promotoria: '',
    email: '',
    status: '',
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

export function CumpleanosAgentesView({
    directory,
}: {
    directory: AgentBirthdayDirectory;
}) {
    const [query, setQuery] = useState('');
    const [filters, setFilters] = useState<ColumnFilters>(EMPTY_FILTERS);
    const normalizedQuery = normalize(query);
    const agents = useMemo(() => (
        directory.agents.filter((agent) => {
            const keysText = agent.definitive_keys.join(' ');
            const promotoriasText = agent.promotorias.join(' ');
            const nextBirthdayText = agent.days_until_birthday === 0
                ? 'hoy 0'
                : `en ${agent.days_until_birthday} días ${agent.days_until_birthday}`;
            const matchesGlobalQuery = !normalizedQuery || [
                agent.agent_name,
                agent.rfc,
                keysText,
                promotoriasText,
                agent.email,
                agent.status,
            ].some((value) => normalize(value).includes(normalizedQuery));

            return matchesGlobalQuery
                && includesFilter(agent.agent_name, filters.agent)
                && includesFilter(agent.rfc, filters.rfc)
                && includesFilter(keysText, filters.keys)
                && (
                    includesFilter(agent.birth_date, filters.birthDate)
                    || includesFilter(displayDate(agent.birth_date), filters.birthDate)
                )
                && includesFilter(nextBirthdayText, filters.nextBirthday)
                && includesFilter(promotoriasText, filters.promotoria)
                && includesFilter(agent.email, filters.email)
                && includesFilter(agent.status, filters.status);
        })
    ), [directory.agents, filters, normalizedQuery]);

    const updateFilter = (field: keyof ColumnFilters, value: string) => {
        setFilters((current) => ({ ...current, [field]: value }));
    };

    const exportToExcel = async () => {
        const XLSX = await import('xlsx');
        const rows = agents.map((agent) => ({
            Agente: agent.agent_name,
            RFC: agent.rfc,
            'Claves definitivas': agent.definitive_keys.join(', '),
            'Fecha de cumpleaños': displayDate(agent.birth_date),
            'Próximo cumpleaños': agent.days_until_birthday === 0
                ? 'Hoy'
                : `En ${agent.days_until_birthday} días`,
            Promotoría: agent.promotorias.join(', '),
            Correo: agent.email,
            Estatus: agent.status,
        }));
        const worksheet = XLSX.utils.json_to_sheet(rows);
        worksheet['!cols'] = [
            { wch: 36 },
            { wch: 16 },
            { wch: 24 },
            { wch: 24 },
            { wch: 22 },
            { wch: 24 },
            { wch: 34 },
            { wch: 18 },
        ];
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Cumpleaños de agentes');
        XLSX.writeFile(
            workbook,
            `cumpleanos-agentes-${directory.generated_on}.xlsx`,
        );
    };

    const filterInput = (field: keyof ColumnFilters, label: string) => (
        <input
            value={filters[field]}
            onChange={(event) => updateFilter(field, event.target.value)}
            onClick={(event) => event.stopPropagation()}
            placeholder={`Filtrar ${label.toLocaleLowerCase('es-MX')}...`}
            aria-label={`Filtrar por ${label}`}
            className="mt-2 w-full min-w-28 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-normal normal-case tracking-normal text-slate-800 outline-none placeholder:text-slate-400 focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
        />
    );

    return (
        <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
            <div className="grid flex-none gap-3 border-b border-slate-200 p-5 sm:grid-cols-3">
                <div className="rounded-xl bg-violet-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-violet-600">Agentes</p>
                    <p className="mt-1 text-2xl font-bold text-slate-900">{directory.summary.total_agents}</p>
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
                        placeholder="Buscar por agente, RFC, clave, promotoría, correo o estatus..."
                        className="w-full rounded-xl border border-slate-300 py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                    />
                </label>
                <p className="whitespace-nowrap text-sm text-slate-500 lg:ml-auto">
                    {agents.length} de {directory.summary.total_agents} agentes
                </p>
                <button
                    type="button"
                    onClick={exportToExcel}
                    disabled={agents.length === 0}
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-violet-200 bg-white px-4 py-2.5 text-sm font-semibold text-violet-700 transition hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <Download className="h-4 w-4" />
                    Exportar a Excel
                </button>
            </div>

            {(directory.summary.invalid_rfc_rows > 0 || directory.summary.missing_rfc_rows > 0) && (
                <div className="mx-5 mt-4 flex flex-none items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                        {directory.summary.missing_rfc_rows} filas sin RFC y {directory.summary.invalid_rfc_rows} con RFC no interpretable fueron omitidas.
                    </span>
                </div>
            )}

            <div className="min-h-0 flex-1 overflow-auto px-5 pb-5">
                <table className="w-full min-w-[1450px] border-separate border-spacing-0 text-left text-sm">
                    <thead className="text-xs uppercase tracking-wide text-slate-600">
                        <tr>
                            <th className="sticky top-0 z-30 min-w-64 rounded-l-lg bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Agente
                                {filterInput('agent', 'Agente')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-44 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                RFC
                                {filterInput('rfc', 'RFC')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-52 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Claves definitivas
                                {filterInput('keys', 'Claves')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-56 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Fecha de cumpleaños
                                {filterInput('birthDate', 'Fecha')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-52 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Próximo cumpleaños
                                {filterInput('nextBirthday', 'Próximo cumpleaños')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-56 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Promotoría
                                {filterInput('promotoria', 'Promotoría')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-72 bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Correo
                                {filterInput('email', 'Correo')}
                            </th>
                            <th className="sticky top-0 z-30 min-w-40 rounded-r-lg bg-slate-100 px-4 py-3 shadow-[0_1px_0_0_#cbd5e1]">
                                Estatus
                                {filterInput('status', 'Estatus')}
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {agents.map((agent) => (
                            <tr key={agent.rfc} className="align-top hover:bg-slate-50">
                                <td className="px-4 py-4 font-semibold text-slate-900">{agent.agent_name}</td>
                                <td className="whitespace-nowrap px-4 py-4 font-mono text-slate-700">{agent.rfc}</td>
                                <td className="px-4 py-4">
                                    <div className="flex flex-wrap gap-1.5">
                                        {agent.definitive_keys.map((key) => (
                                            <span key={key} className="rounded-full bg-violet-50 px-2.5 py-1 text-xs font-medium text-violet-700">
                                                {key}
                                            </span>
                                        ))}
                                    </div>
                                </td>
                                <td className="whitespace-nowrap px-4 py-4 text-slate-700">{displayDate(agent.birth_date)}</td>
                                <td className="px-4 py-4">
                                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap font-medium text-pink-700">
                                        <CakeSlice className="h-4 w-4" />
                                        {agent.days_until_birthday === 0 ? 'Hoy' : `En ${agent.days_until_birthday} días`}
                                    </span>
                                </td>
                                <td className="px-4 py-4 font-medium text-slate-700">{agent.promotorias.join(', ') || 'Sin asignar'}</td>
                                <td className="px-4 py-4 text-slate-700">{agent.email || 'Sin correo'}</td>
                                <td className="whitespace-nowrap px-4 py-4 text-slate-700">{agent.status || 'Sin estatus'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {agents.length === 0 && (
                    <div className="py-16 text-center text-slate-500">
                        No hay agentes que coincidan con la búsqueda.
                    </div>
                )}
            </div>
        </div>
    );
}
