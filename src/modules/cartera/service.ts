import { fetchFromApi } from '@/lib/api';
import { ClientProfile, CarteraMetlifeVida, CarteraMetlifeGMM, CarteraSura } from '@/lib/types/cartera';

export async function searchClients(query: string): Promise<ClientProfile[]> {
    if (!query) return [];

    const queryString = new URLSearchParams({ query }).toString();
    const results = await fetchFromApi<any[]>(`/cartera/search?${queryString}`);

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

export async function getCarteraData(
    insurer: string,
    type: string = 'ALL'
): Promise<(CarteraMetlifeVida | CarteraMetlifeGMM | CarteraSura)[]> {
    const params = new URLSearchParams({
        insurer,
        type
    });

    return fetchFromApi<(CarteraMetlifeVida | CarteraMetlifeGMM | CarteraSura)[]>(`/cartera/data?${params.toString()}`);
}
