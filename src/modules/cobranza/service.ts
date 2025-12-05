import { fetchFromApi } from '@/lib/api';
import { MetlifeVidaRaw, MetlifeGMMRaw } from '@/lib/types/metlife';

export async function getCobranzaVida(): Promise<MetlifeVidaRaw[]> {
    return fetchFromApi<MetlifeVidaRaw[]>('/cobranza/vida');
}

export async function getCobranzaGMM(): Promise<MetlifeGMMRaw[]> {
    return fetchFromApi<MetlifeGMMRaw[]>('/cobranza/gmm');
}

export async function updateCobranzaVida(data: MetlifeVidaRaw[]): Promise<void> {
    // TODO: Implement update endpoint in Python if needed
    console.warn("Update not implemented in Python backend yet");
}

export async function updateCobranzaGMM(data: MetlifeGMMRaw[]): Promise<void> {
    // TODO: Implement update endpoint in Python if needed
    console.warn("Update not implemented in Python backend yet");
}

// Placeholder for logic to match payments
export function reconcilePayments(policies: MetlifeVidaRaw[], payments: any[]) {
    // TODO: Implement reconciliation logic
    // This requires knowing the format of the "monthly billing statements" from insurers
    // which is mentioned in the prompt but not detailed with a file path.
    // For now, we assume we are just loading/updating the base.
    return policies;
}
