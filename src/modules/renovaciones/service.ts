import { fetchFromApi } from '@/lib/api';
import { RenovacionGMM, RenovacionVida, RenovacionSura } from '@/lib/types/renovaciones';

export async function getUpcomingRenewals(
    days: number = 30,
    type: string = 'ALL',
    insurer: string = 'Metlife',
    startDate?: string,
    endDate?: string
): Promise<(RenovacionGMM | RenovacionVida | RenovacionSura)[]> {
    const params: Record<string, string> = {
        days: days.toString(),
        type,
        insurer
    };

    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const queryString = new URLSearchParams(params).toString();
    console.log(`Fetching Renovaciones: /renovaciones/upcoming?${queryString}`);

    return fetchFromApi<(RenovacionGMM | RenovacionVida | RenovacionSura)[]>(`/renovaciones/upcoming?${queryString}`);
}

export async function updateRenewalStatus(
    insurer: string,
    type: string,
    policyNumber: string | number,
    newStatus: string,
    expediente?: string
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
            expediente
        }),
    });
}
