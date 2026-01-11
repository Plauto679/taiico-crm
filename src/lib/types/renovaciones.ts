export interface RenovacionGMM {
    NPOLIZA: string;
    POLORIG: string;
    CONTRATANTE: string;
    FFINVIG: string; // Date YYYY-MM-DD
    'PRIMA.1': number;
    IVA: number;
    NOMBREL: string; // Asegurado
    DEDUCIBLE: number;
    PAGADOHASTA: string; // Date YYYY-MM-DD
    COASEGURO?: number; // Optional as it wasn't strictly in the display list but is useful
    ESTATUS_DE_RENOVACION?: string;
    EXPEDIENTE?: string;
    Email?: string;
}

export interface RenovacionVida {
    POLIZA_ACTUAL: string;
    CONTRATANTE: string;
    INI_VIG: string; // Date YYYY-MM-DD
    FIN_VIG: string; // Date YYYY-MM-DD
    FORMA_PAGO: string;
    CONDUCTO_COBRO: string;
    AGENTE: string;
    PRIMA_ANUAL: number;
    PRIMA_MODAL: number;
    PAGADO_HASTA: string; // Date YYYY-MM-DD
    ESTATUS_DE_RENOVACION?: string;
    EXPEDIENTE?: string;
    Email?: string;
}

export interface RenovacionSura {
    POLIZA: string;
    NOMBRE: string;
    'INICIO VIGENCIA': string; // Date YYYY-MM-DD
    'FIN VIGENCIA': string; // Date YYYY-MM-DD
    RAMO: string;
    PRIMA: number;
    PERIODICIDAD_PAGO: string;
    PROSPECTADOR: string;
    ESTATUS_DE_RENOVACION: string;
    EXPEDIENTE?: string;
    Email?: string;
}

export interface RenovacionAarco {
    POLIZA: string;
    ASEGURADORA: string;
    PROMOTORIA: string;
    AGENTE: string;
    PROSPECTADOR: string;
    RAMO: string;
    PRODUCTO: string;
    CONTRATANTE: string;
    ASEGURADO: string;
    'INICIO VIGENCIA': string; // Date YYYY-MM-DD
    'FIN VIGENCIA': string; // Date YYYY-MM-DD
    'PRIMA NETA ANUAL': number;
    ESTATUS_DE_RENOVACION: string; // Mapped from ESTATUS in backend
    EXPEDIENTE?: string;
    Email?: string;
}

// Union type for cases where we might handle them generically, though usually we won't
export type RenewalItem = RenovacionGMM | RenovacionVida | RenovacionSura | RenovacionAarco;
