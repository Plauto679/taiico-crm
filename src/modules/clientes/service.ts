import { fetchFromApi } from '@/lib/api';
import { Cliente, ClientRegistryAudit } from '@/lib/types/clientes';

export async function getClients(): Promise<Cliente[]> {
    return fetchFromApi('/clientes/');
}

export async function addClient(client: Cliente): Promise<Cliente> {
    return fetchFromApi('/clientes/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(client),
    });
}

export async function updateClient(clientId: string | null | undefined, originalNombre: string, client: Cliente): Promise<any> {
    return fetchFromApi('/clientes/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ client_id: clientId, original_nombre: originalNombre, client }),
    });
}

export async function deleteClient(clientId: string | null | undefined, nombre: string): Promise<any> {
    return fetchFromApi('/clientes/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ client_id: clientId, nombre }),
    });
}
export async function getClientRegistryAudit(): Promise<ClientRegistryAudit> {
    return fetchFromApi('/clientes/registry-audit');
}

export async function syncClientFolderLinks(): Promise<{ linked_count: number }> {
    return fetchFromApi('/clientes/sync-expedientes', { method: 'POST' });
}
export async function searchClient(name: string): Promise<{ email: string | null }> {
    return fetchFromApi(`/clientes/search?name=${encodeURIComponent(name)}`);
}
