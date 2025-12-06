export interface RenewalItem {
    // Shared fields
    poliza: string;
    polizaOrigen?: string;
    contratante: string;
    rfcContratante?: string;

    // Dates (ISO strings YYYY-MM-DD)
    fechaInicioVigencia?: string;
    fechaFinVigencia?: string;
    fechaRenovacion: string; // Canonical date
    pagadoHasta?: string;

    // Classification
    ramo: 'VIDA' | 'GMM';
    estatus: string;
    agente: string;

    // Money (Numbers)
    prima?: number;
    iva?: number;
    deducible?: number;

    // GMM Specific
    nombreAsegurado?: string;
    coaseguro?: number; // Decimal (0-1)

    // Vida Specific
    producto?: string;
    formaPago?: string;
    conductoCobro?: string;
}

// Raw interfaces are no longer strictly needed for the service mapping 
// since the backend does the heavy lifting, but we can keep them if we want strict typing for the API response
// For now, the API returns objects that match RenewalItem directly (or close to it).
