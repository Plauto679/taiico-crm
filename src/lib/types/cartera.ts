export interface CarteraVidaRaw {
    Poliza: number;
    Contratante: string;
    PROSPECTADOR: string;
    PORCENTAJE: number;
}

export interface CarteraGMMRaw {
    POLIZA: number;
    "Poliza actual": string;
    Contratante: string;
    PROSPECTADOR: string;
    PORCENTAJE: number;
}

export interface ClientProfile {
    id: string; // Generated ID
    nombre: string;
    polizas: {
        numero: string;
        ramo: 'VIDA' | 'GMM';
        estatus: string;
        renovacion: Date | null;
    }[];
    prospectador: string;
}
