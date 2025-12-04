import { loadExcelSheet } from '@/lib/excel/loader';
import { PATHS } from '@/lib/config';
import { CarteraVidaRaw, CarteraGMMRaw, ClientProfile } from '@/lib/types/cartera';

export async function getClientProfile(query: string): Promise<ClientProfile[]> {
    const vidaRaw = await loadExcelSheet<CarteraVidaRaw>(PATHS.METLIFE.CARTERA, 'Vida');
    const gmmRaw = await loadExcelSheet<CarteraGMMRaw>(PATHS.METLIFE.CARTERA, 'GMM');

    // Simple search by name or policy
    const lowerQuery = query.toLowerCase();

    const vidaMatches = vidaRaw.filter(row =>
        row.Contratante?.toLowerCase().includes(lowerQuery) ||
        row.Poliza?.toString().includes(lowerQuery)
    );

    const gmmMatches = gmmRaw.filter(row =>
        row.Contratante?.toLowerCase().includes(lowerQuery) ||
        row.POLIZA?.toString().includes(lowerQuery)
    );

    // Map to ClientProfile
    // Note: This is a simplified view. In reality, we'd want to group by client.
    // For now, returning individual policy matches as profiles.

    const profiles: ClientProfile[] = [];

    vidaMatches.forEach(row => {
        profiles.push({
            id: `VIDA-${row.Poliza}`,
            nombre: row.Contratante,
            polizas: [{
                numero: row.Poliza?.toString(),
                ramo: 'VIDA',
                estatus: 'Active', // Placeholder
                renovacion: null // Placeholder, would need to join with Renovaciones
            }],
            prospectador: row.PROSPECTADOR
        });
    });

    gmmMatches.forEach(row => {
        profiles.push({
            id: `GMM-${row.POLIZA}`,
            nombre: row.Contratante,
            polizas: [{
                numero: row.POLIZA?.toString(),
                ramo: 'GMM',
                estatus: 'Active',
                renovacion: null
            }],
            prospectador: row.PROSPECTADOR
        });
    });

    return profiles;
}
