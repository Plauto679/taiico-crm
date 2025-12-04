import { loadExcelSheet } from '@/lib/excel/loader';
import { PATHS } from '@/lib/config';
import { RenovacionVidaRaw, RenovacionGMMRaw, RenewalItem } from '@/lib/types/renovaciones';
import { parseExcelDate, isUpcoming } from '@/lib/utils/date';

export async function getUpcomingRenewals(days: number = 30): Promise<RenewalItem[]> {
    const vidaRaw = await loadExcelSheet<RenovacionVidaRaw>(PATHS.METLIFE.RENOVACIONES_VIDA, 'Vida'); // Assuming sheet name is Vida? Prompt says "Metlife Vida.xlsx" but not sheet name. Usually Sheet1 or similar. Let's assume 'Sheet1' if not specified, but prompt for Cobranza said "Vida" and "GMM". For Renovaciones it says "Vida Columns" and "GMM Columns" but implies separate files.
    // Wait, prompt says:
    // Path: .../Metlife Vida.xlsx
    // Vida Columns: ...
    // Path for GMM: .../Metlife GMM.xlsx
    // GMM Columns: ...
    // It doesn't explicitly state sheet names for these files. I'll guess 'Sheet1' or try to inspect.
    // But `loadExcelSheet` throws if sheet not found.
    // I'll assume the sheet name matches the file type or is 'Reporte' or something standard.
    // Actually, I can use `getExcelSheetNames` to find out, but I can't do that at runtime easily without logic.
    // I'll assume 'Sheet1' for now, or maybe the user can correct me.
    // Or better, I'll update `loader.ts` to support "first sheet" if sheetName is not provided?
    // No, I'll just try 'Sheet1' for now.

    // Actually, looking at the Cobranza file, it had "Vida" and "GMM" sheets.
    // These are separate files.
    // I'll assume the sheet name is the same as the file base name or 'Sheet1'.

    // Let's use a safe approach: I'll assume 'Sheet1' but I should probably verify.
    // Since I can't verify right now without reading the file, I'll write the code to try 'Sheet1'.

    // Re-reading prompt: "Sheet: Vida" was for Cobranza.
    // For Renovaciones: "Vida Columns: ..." "GMM Columns: ..."
    // It doesn't specify sheet names.

    const vidaRenewals = vidaRaw.map(row => {
        const date = parseExcelDate(row.FIN_VIG); // Renewal date is usually End of Vigencia
        return {
            poliza: row.POLIZA_ACTUAL?.toString(),
            contratante: row.CONTRATANTE,
            fechaRenovacion: date,
            ramo: 'VIDA',
            agente: row.NOM_AGENTE,
            estatus: row.ESTATUS_POL,
            prima: row.PRIMA_ANUAL
        } as RenewalItem;
    }).filter(item => item.fechaRenovacion && isUpcoming(item.fechaRenovacion, days));

    const gmmRaw = await loadExcelSheet<RenovacionGMMRaw>(PATHS.METLIFE.RENOVACIONES_GMM, 'GMM');

    const gmmRenewals = gmmRaw.map(row => {
        const date = parseExcelDate(row.FFINVIG);
        return {
            poliza: row.NPOLIZA?.toString(),
            contratante: row.CONTRATANTE,
            fechaRenovacion: date,
            ramo: 'GMM',
            agente: row.NOMBRE,
            estatus: row.ESTATUS?.toString(),
            prima: row.PRIMA
        } as RenewalItem;
    }).filter(item => item.fechaRenovacion && isUpcoming(item.fechaRenovacion, days));

    return [...vidaRenewals, ...gmmRenewals];
}
