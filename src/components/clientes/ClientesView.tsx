'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Cliente, ClientRegistryAudit } from '@/lib/types/clientes';
import { DataTable } from '@/components/ui/DataTable';
import { AddClientModal } from './AddClientModal';
import { EditClientModal } from './EditClientModal';
import { addClient, updateClient, deleteClient, getClientRegistryAudit, syncClientFolderLinks } from '@/modules/clientes/service';
import { AlertTriangle, ExternalLink, RefreshCw, Search, ShieldCheck, UserPlus } from 'lucide-react';

interface ClientesViewProps {
    initialClients: Cliente[];
}

export function ClientesView({ initialClients }: ClientesViewProps) {
    const router = useRouter();
    const [clients, setClients] = useState<Cliente[]>(initialClients);
    const [searchTerm, setSearchTerm] = useState('');
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [selectedClient, setSelectedClient] = useState<Cliente | null>(null);
    const [audit, setAudit] = useState<ClientRegistryAudit | null>(null);
    const [isAuditing, setIsAuditing] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);

    useEffect(() => setClients(initialClients), [initialClients]);

    const filteredClients = clients.filter(client =>
        client.nombre.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (client.rfc && client.rfc.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (client.correo && client.correo.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const handleAddClient = async (newClient: Cliente) => {
        await addClient(newClient);
        router.refresh();
    };

    const handleUpdateClient = async (originalNombre: string, updatedClient: Cliente) => {
        await updateClient(selectedClient?.id, originalNombre, updatedClient);
        router.refresh();
    };

    const handleDeleteClient = async (nombre: string) => {
        await deleteClient(selectedClient?.id, nombre);
        router.refresh();
    };

    const runAudit = async () => {
        setIsAuditing(true);
        try {
            setAudit(await getClientRegistryAudit());
        } finally {
            setIsAuditing(false);
        }
    };

    const syncSafeLinks = async () => {
        setIsSyncing(true);
        try {
            const result = await syncClientFolderLinks();
            alert(`${result.linked_count} expedientes vinculados de forma segura.`);
            router.refresh();
            setAudit(await getClientRegistryAudit());
        } finally {
            setIsSyncing(false);
        }
    };

    const columns = [
        { header: 'Nombre', accessorKey: 'nombre' as keyof Cliente },
        { header: 'RFC', accessorKey: 'rfc' as keyof Cliente },
        { header: 'Correo', accessorKey: 'correo' as keyof Cliente },
        { header: 'Teléfono', accessorKey: 'telefono' as keyof Cliente },
        {
            header: 'Estado',
            filterValue: (client: Cliente) => client.estado_identidad === 'identified' ? 'Cliente identificado' : 'Prospecto',
            accessorKey: (client: Cliente) => (
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${client.estado_identidad === 'identified' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {client.estado_identidad === 'identified' ? 'Cliente identificado' : 'Prospecto'}
                </span>
            ),
        },
        {
            header: 'Expediente',
            filterValue: (client: Cliente) => client.expediente_url ? 'Vinculado' : 'Sin vincular',
            accessorKey: (client: Cliente) => client.expediente_url ? (
                <a href={client.expediente_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:text-blue-800">
                    Abrir <ExternalLink className="h-3.5 w-3.5" />
                </a>
            ) : <span className="text-slate-400">Sin vincular</span>,
        },
    ];

    return (
        <div className="flex h-full min-h-0 flex-col gap-6 overflow-hidden">
            <div className="flex flex-none flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-lg shadow-sm">
                <div className="relative flex-1 max-w-md">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                        type="text"
                        placeholder="Buscar cliente..."
                        className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="flex flex-wrap gap-2">
                    <button onClick={runAudit} disabled={isAuditing} className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                        <ShieldCheck className="mr-2 h-5 w-5" /> {isAuditing ? 'Auditando...' : 'Auditar expedientes'}
                    </button>
                    <button onClick={() => setIsAddModalOpen(true)} className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                        <UserPlus className="h-5 w-5 mr-2" /> Nuevo Cliente
                    </button>
                </div>
            </div>

            {audit && (
                <section className="max-h-[42%] flex-none overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900">Auditoría del registro maestro</h2>
                            <p className="text-sm text-slate-500">Solo lectura: no mueve, renombra ni elimina carpetas de Drive.</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <a href={audit.drive_folder_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Abrir Drive <ExternalLink className="h-4 w-4" /></a>
                            <button onClick={syncSafeLinks} disabled={isSyncing || !audit.summary.safe_links_available} className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} /> Vincular {audit.summary.safe_links_available} coincidencias seguras</button>
                        </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <AuditCard label="Clientes" value={audit.summary.total_clients} />
                        <AuditCard label="Prospectos sin RFC" value={audit.summary.prospects_without_rfc} warning />
                        <AuditCard label="Clientes vinculados" value={audit.summary.linked_clients} />
                        <AuditCard label="Vínculos seguros pendientes" value={audit.summary.safe_links_available} />
                        <AuditCard label="RFC duplicados en Clientes" value={audit.summary.duplicate_client_rfcs} warning />
                        <AuditCard label="RFC duplicados en Drive" value={audit.summary.duplicate_drive_rfcs} warning />
                        <AuditCard label="Carpetas sin cliente registrado" value={audit.summary.unregistered_drive_folders} warning />
                        <AuditCard label="Carpetas con nombre no reconocido" value={audit.summary.malformed_drive_folders} warning />
                    </div>
                    {(audit.details.duplicate_client_rfcs.length > 0 || audit.details.duplicate_drive_rfcs.length > 0) && (
                        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                            <p className="flex items-center gap-2 font-bold"><AlertTriangle className="h-4 w-4" /> Duplicados que requieren revisión manual</p>
                            {audit.details.duplicate_client_rfcs.map((item) => <p key={`client-${item.rfc}`} className="mt-2"><strong>{item.rfc}</strong> en Clientes: {item.clients.map((client) => client.nombre).join(' · ')}</p>)}
                            {audit.details.duplicate_drive_rfcs.map((item) => <p key={`drive-${item.rfc}`} className="mt-2"><strong>{item.rfc}</strong> en Drive: {item.folders.map((folder) => folder.name).join(' · ')}</p>)}
                        </div>
                    )}
                </section>
            )}

            <div className="min-h-0 flex-1 overflow-hidden rounded-lg bg-white shadow">
                <DataTable
                    data={filteredClients}
                    columns={columns}
                    filterMode="multi-select"
                    className="h-full max-w-full overflow-auto border-0 shadow-none"
                    onRowClick={(row) => setSelectedClient(row)}
                />
            </div>

            <AddClientModal
                isOpen={isAddModalOpen}
                onClose={() => setIsAddModalOpen(false)}
                onSave={handleAddClient}
            />

            <EditClientModal
                isOpen={!!selectedClient}
                onClose={() => setSelectedClient(null)}
                client={selectedClient}
                onSave={handleUpdateClient}
                onDelete={handleDeleteClient}
            />
        </div>
    );
}

function AuditCard({ label, value, warning = false }: { label: string; value: number; warning?: boolean }) {
    return <div className={`rounded-lg border p-3 ${warning && value ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-slate-50'}`}><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold text-slate-900">{value.toLocaleString('es-MX')}</p></div>;
}
