import { fetchFromApi } from '@/lib/api';
import { RenewalItem, RenovacionGMM, RenovacionVida } from '@/lib/types/renovaciones';

export async function getUpcomingRenewals(
    days: number = 30,
    type: 'ALL' | 'VIDA' | 'GMM' = 'ALL',
    insurer: string = 'Metlife',
    startDate?: string,
    endDate?: string
): Promise<RenewalItem[]> {
    const params: Record<string, string> = {
        days: days.toString(),
        type,
        insurer
    };

    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const queryString = new URLSearchParams(params).toString();

    // The backend returns a list of objects matching the requested schema
    return fetchFromApi<RenewalItem[]>(`/renovaciones/upcoming?${queryString}`);
}

export async function updateRenewalStatus(
    insurer: string,
    type: string,
    policyNumber: string,
    newStatus: string
): Promise<void> {
    await fetchFromApi('/renovaciones/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            insurer,
            type,
            policy_number: policyNumber,
            new_status: newStatus,
        }),
    });
}
