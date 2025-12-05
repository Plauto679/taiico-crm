import { fetchFromApi } from '@/lib/api';
import { RenovacionVidaRaw, RenovacionGMMRaw, RenewalItem } from '@/lib/types/renovaciones';

export async function getUpcomingRenewals(days: number = 30): Promise<RenewalItem[]> {
    const [vidaRaw, gmmRaw] = await Promise.all([
        fetchFromApi<RenovacionVidaRaw[]>('/renovaciones/vida', { days }),
        fetchFromApi<RenovacionGMMRaw[]>('/renovaciones/gmm', { days })
    ]);

    const renewals: RenewalItem[] = [];

    // Map Vida
    vidaRaw.forEach(item => {
        renewals.push({
            poliza: item.POLIZA_ACTUAL?.toString(),
            contratante: item.CONTRATANTE,
            fechaRenovacion: item.FIN_VIG, // Assuming FIN_VIG is the renewal date
            ramo: 'VIDA',
            agente: item.NOM_AGENTE,
            estatus: item.ESTATUS_POL,
            prima: item.PRIMA_ANUAL
        } as RenewalItem);
    });

    // Map GMM
    gmmRaw.forEach(item => {
        renewals.push({
            poliza: item.NPOLIZA?.toString(),
            contratante: item.CONTRATANTE,
            fechaRenovacion: item.FFINVIG?.toString(), // Assuming FFINVIG is the renewal date
            ramo: 'GMM',
            agente: item.NOMBRE,
            estatus: item.ESTATUS?.toString(),
            prima: item.PRIMA
        } as RenewalItem);
    });

    return renewals;
}
