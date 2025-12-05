import { fetchFromApi } from '@/lib/api';
import { ClientProfile } from '@/lib/types/cartera';

export async function searchClients(query: string): Promise<ClientProfile[]> {
    if (!query) return [];

    const results = await fetchFromApi<any[]>('/cartera/search', { query });

    return results.map(item => ({
        id: `${item['Tipo']}-${item['Póliza'] || item['# de Póliza']}`,
        nombre: item['Nombre'] || item['Contratante'],
        prospectador: item['Prospectador'] || '', // Handle missing field
        polizas: [{
            numero: (item['Póliza'] || item['# de Póliza'])?.toString(),
            ramo: item['Tipo'] as 'VIDA' | 'GMM',
            estatus: item['Estatus'] || item['Estatus Póliza'],
            renovacion: null // Placeholder
        }]
    }));
}
