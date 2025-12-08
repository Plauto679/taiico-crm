export interface ClientProfile {
    id: string;
    nombre: string;
    prospectador: string;
    polizas: {
        numero: string;
        ramo: 'VIDA' | 'GMM';
        estatus: string;
        renovacion: {
            fecha: string;
            estatus: string;
        } | null;
    }[];
}

export interface CarteraMetlifeVida {
    'Poliza': number;
    'Contratante': string;
    'PROSPECTADOR ': string;
    'PORCENTAJE ': number;
}

export interface CarteraMetlifeGMM {
    'POLIZA ': number;
    'Poliza actual': string;
    'Contratante': string;
    'PROSPECTADOR ': string;
    'PORCENTAJE': number;
}

export interface CarteraSura {
    'PÓLIZA': number;
    'PROSPECTADOR': string;
    'PORCENTAJE': number;
}
