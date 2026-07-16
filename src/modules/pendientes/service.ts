import { fetchFromApi } from '@/lib/api';
import { PendingSourceData } from '@/lib/types/pendientes';

export function getPendingSource(
    source: 'emision-servicios' | 'siniestros',
): Promise<PendingSourceData> {
    return fetchFromApi<PendingSourceData>(`/pendientes/${source}`);
}
