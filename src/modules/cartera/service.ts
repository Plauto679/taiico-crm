import { fetchFromApi } from '@/lib/api';
import { CarteraRecord, CarteraRecordInput, ClientProfile } from '@/lib/types/cartera';

export async function searchClients(query: string): Promise<ClientProfile[]> {
    if (!query) return [];
    const results = await fetchFromApi<any[]>(`/cartera/search?${new URLSearchParams({ query })}`);
    return results.map((item) => ({
        id: `${item.ramo}-${item.poliza}`,
        nombre: item.contratante,
        prospectador: '',
        polizas: [{ numero: item.poliza, ramo: item.ramo, estatus: item.estatus, renovacion: null }],
    }));
}

export async function getCarteraData(insurer: string, type = 'ALL'): Promise<CarteraRecord[]> {
    return fetchFromApi<CarteraRecord[]>(`/cartera/data?${new URLSearchParams({ insurer, type })}`);
}

export async function createCarteraRecord(payload: CarteraRecordInput): Promise<CarteraRecord> {
    return fetchFromApi<CarteraRecord>('/cartera/records', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function updateCarteraRecord(id: string, payload: CarteraRecordInput): Promise<CarteraRecord> {
    return fetchFromApi<CarteraRecord>(`/cartera/records/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}
