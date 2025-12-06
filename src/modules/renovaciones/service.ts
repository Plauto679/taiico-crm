import { fetchFromApi } from '@/lib/api';
import { RenewalItem } from '@/lib/types/renovaciones';

export async function getUpcomingRenewals(
    days: number = 30,
    type: 'ALL' | 'VIDA' | 'GMM' = 'ALL',
    insurer: string = 'Metlife'
): Promise<RenewalItem[]> {
    // The backend now handles the unified schema and filtering
    // We just need to pass the parameters
    return fetchFromApi<RenewalItem[]>('/renovaciones/upcoming', { days, type, insurer });
}
