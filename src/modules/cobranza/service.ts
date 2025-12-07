import { fetchFromApi } from '@/lib/api';
import { MetlifeVidaRaw, MetlifeGMMRaw } from '@/lib/types/metlife';

export async function getCobranzaVida(startDate?: string, endDate?: string): Promise<MetlifeVidaRaw[]> {
    let url = '/cobranza/vida';
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);

    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    return fetchFromApi<MetlifeVidaRaw[]>(url);
}

export async function getCobranzaGMM(startDate?: string, endDate?: string): Promise<MetlifeGMMRaw[]> {
    let url = '/cobranza/gmm';
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);

    if (params.toString()) {
        url += `?${params.toString()}`;
    }

    return fetchFromApi<MetlifeGMMRaw[]>(url);
}
