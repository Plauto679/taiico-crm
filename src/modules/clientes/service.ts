import { fetchFromApi } from '@/lib/api';
import { Cliente } from '@/lib/types/clientes';

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

export async function updateClient(originalNombre: string, client: Cliente): Promise<any> {
    return fetchFromApi('/clientes/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ original_nombre: originalNombre, client }),
    });
}

export async function deleteClient(nombre: string): Promise<any> {
    return fetchFromApi('/clientes/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ nombre }),
    });
}
export async function searchClient(name: string): Promise<{ email: string | null }> {
    return fetchFromApi(`/clientes/search?name=${encodeURIComponent(name)}`);
}
