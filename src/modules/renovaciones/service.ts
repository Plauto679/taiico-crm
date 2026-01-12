import { fetchFromApi } from '@/lib/api';
import { RenovacionGMM, RenovacionVida, RenovacionSura, RenovacionAarco } from '@/lib/types/renovaciones';

export async function getUpcomingRenewals(
    days: number = 30,
    type: string = 'ALL',
    insurer: string = 'Metlife',
    startDate?: string,
    endDate?: string
): Promise<(RenovacionGMM | RenovacionVida | RenovacionSura | RenovacionAarco)[]> {
    const params: Record<string, string> = {
        days: days.toString(),
        type,
        insurer
    };

    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    const queryString = new URLSearchParams(params).toString();
    console.log(`Fetching Renovaciones: /renovaciones/upcoming?${queryString}`);

    return fetchFromApi<(RenovacionGMM | RenovacionVida | RenovacionSura | RenovacionAarco)[]>(`/renovaciones/upcoming?${queryString}`);
}

export async function updateRenewalStatus(
    insurer: string,
    type: string,
    policyNumber: string | number,
    newStatus: string | null,
    expediente: string | null,
    email?: string | null
): Promise<any> {
    const payload: any = {
        insurer,
        type,
        policy_number: policyNumber,
    };

    if (newStatus) payload.new_status = newStatus;
    if (expediente !== null) payload.expediente = expediente;
    if (email !== null && email !== undefined) payload.email = email;

    const response = await fetchFromApi('/renovaciones/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    return response;
}

export async function sendRenewalEmail(
    insurer: string,
    type: string,
    policyNumber: string | number,
    clientName: string,
    endDate: string,
    expediente?: string
): Promise<any> {
    return fetchFromApi('/renovaciones/send-email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            insurer,
            type,
            policy_number: policyNumber,
            client_name: clientName,
            end_date: endDate,
            expediente: expediente
        }),
    });
}
