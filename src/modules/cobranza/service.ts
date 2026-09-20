import { fetchFromApi } from '@/lib/api';
import { CobranzaVida, CobranzaGMM, CobranzaSura } from '@/lib/types/cobranza';

export async function getCobranzaVida(startDate?: string, endDate?: string, insurer: string = 'Metlife'): Promise<CobranzaVida[] | CobranzaSura[]> {
    const params: Record<string, string> = { insurer };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const queryString = new URLSearchParams(params).toString();

    if (insurer === 'SURA') {
        return fetchFromApi<CobranzaSura[]>(`/cobranza/vida?${queryString}`);
    }

    return fetchFromApi<CobranzaVida[]>(`/cobranza/vida?${queryString}`);
}

export async function getCobranzaGMM(startDate?: string, endDate?: string, insurer: string = 'Metlife'): Promise<CobranzaGMM[] | CobranzaSura[]> {
    const params: Record<string, string> = { insurer };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const queryString = new URLSearchParams(params).toString();

    if (insurer === 'SURA') {
        return fetchFromApi<CobranzaSura[]>(`/cobranza/gmm?${queryString}`);
    }

    return fetchFromApi<CobranzaGMM[]>(`/cobranza/gmm?${queryString}`);
}

export async function getMetlifeCollectionBase(branch: 'VIDA' | 'GMM', startDate?: string, endDate?: string) {
    const params = new URLSearchParams({ branch });
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    return fetchFromApi<import('@/lib/types/cobranza').CobranzaMetlifeBase[]>(`/cobranza/metlife/base?${params}`);
}
