import { loadExcelSheet } from '@/lib/excel/loader';
import { writeExcelSheet } from '@/lib/excel/writer';
import { PATHS } from '@/lib/config';
import { MetlifeVidaRaw, MetlifeGMMRaw } from '@/lib/types/metlife';

export async function loadCobranzaVida() {
    return loadExcelSheet<MetlifeVidaRaw>(PATHS.METLIFE.COBRANZA, 'Vida');
}

export async function loadCobranzaGMM() {
    return loadExcelSheet<MetlifeGMMRaw>(PATHS.METLIFE.COBRANZA, 'GMM');
}

export async function updateCobranzaVida(data: MetlifeVidaRaw[]) {
    return writeExcelSheet(PATHS.METLIFE.COBRANZA, 'Vida', data);
}

export async function updateCobranzaGMM(data: MetlifeGMMRaw[]) {
    return writeExcelSheet(PATHS.METLIFE.COBRANZA, 'GMM', data);
}

// Placeholder for logic to match payments
export function reconcilePayments(policies: MetlifeVidaRaw[], payments: any[]) {
    // TODO: Implement reconciliation logic
    // This requires knowing the format of the "monthly billing statements" from insurers
    // which is mentioned in the prompt but not detailed with a file path.
    // For now, we assume we are just loading/updating the base.
    return policies;
}
