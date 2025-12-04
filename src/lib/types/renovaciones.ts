export interface RenovacionVidaRaw {
    CONTRATANTE: string;
    RAMO: number;
    POLIZA_ORIGEN: number;
    FPLAN: string;
    PDESC: string;
    ESTATUS_POL: string;
    POLIZA_ACTUAL: number;
    RFC_CONTRATANTE: string;
    INI_VIG: string;
    FIN_VIG: string;
    FORMA_PAGO: string;
    CONDUCTO_COBRO: string;
    PROMOTORIA: number;
    AGENTE: number;
    NOM_AGENTE: string;
    PRIMA_ANUAL: number;
    PRIMA_MODAL: number;
    MONEDA: string;
    PAGADO_HASTA: string;
}

export interface RenovacionGMMRaw {
    CONTRATANTE: string;
    RFC: string;
    RAMSUBRAMO: number;
    PRODUCTO: string;
    NPOLIZA: number;
    POLORIG: number;
    FINIVIG: number | string; // Excel date
    FFINVIG: number | string; // Excel date
    NESQFPAGO: number;
    NOMBREL: string;
    ESTATUS: number;
    CONDCOB: string;
    PROMOTORIA: number;
    AGENTE: number;
    NOMBRE: string;
    PRIMA: number;
    "PRIMA.1": number; // Note: Excel duplicate column name handling?
    RECARGO: number;
    GTOSEXP: number;
    IVA: number;
    MONEDA: string;
    PAGADOHASTA: number | string;
    DEDUCIBLE: number;
    COASEGURO: number;
}

export interface RenewalItem {
    poliza: string;
    contratante: string;
    fechaRenovacion: Date;
    ramo: 'VIDA' | 'GMM';
    agente: string;
    estatus: string;
    prima: number;
}
