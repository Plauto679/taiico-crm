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
