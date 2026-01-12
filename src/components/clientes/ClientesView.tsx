'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Cliente } from '@/lib/types/clientes';
import { DataTable } from '@/components/ui/DataTable';
import { AddClientModal } from './AddClientModal';
import { addClient } from '@/modules/clientes/service';
import { Search, UserPlus } from 'lucide-react';

interface ClientesViewProps {
    initialClients: Cliente[];
}

export function ClientesView({ initialClients }: ClientesViewProps) {
    const router = useRouter();
    const [clients] = useState<Cliente[]>(initialClients);
    const [searchTerm, setSearchTerm] = useState('');
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

    const filteredClients = clients.filter(client =>
        client.nombre.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (client.correo && client.correo.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const handleAddClient = async (newClient: Cliente) => {
        await addClient(newClient);
        router.refresh();
    };

    const columns = [
        { header: 'Nombre', accessorKey: 'nombre' as keyof Cliente },
        { header: 'Correo', accessorKey: 'correo' as keyof Cliente },
        { header: 'Teléfono', accessorKey: 'telefono' as keyof Cliente },
    ];

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-lg shadow-sm">
                <div className="relative flex-1 max-w-md">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                        type="text"
                        placeholder="Buscar cliente..."
                        className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <button
                    onClick={() => setIsAddModalOpen(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                    <UserPlus className="h-5 w-5 mr-2" />
                    Nuevo Cliente
                </button>
            </div>

            <div className="bg-white rounded-lg shadow overflow-hidden">
                <DataTable
                    data={filteredClients}
                    columns={columns}
                />
            </div>

            <AddClientModal
                isOpen={isAddModalOpen}
                onClose={() => setIsAddModalOpen(false)}
                onSave={handleAddClient}
            />
        </div>
    );
}
