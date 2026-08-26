export interface ClientProfile {
    id: string;
    nombre: string;
    prospectador: string;
    polizas: {
        numero: string;
        ramo: 'VIDA' | 'GMM';
        estatus: string;
        renovacion: { fecha: string; estatus: string } | null;
    }[];
}

export interface CarteraRecord {
    id: string;
    policy_number: string;
    current_policy_number: string;
    contractor: string;
    prospector: string;
    percentage: number;
    payment_start_date: string | null;
    insurer: string;
    policy_type: string;
}

export type CarteraRecordInput = Omit<CarteraRecord, 'id'>;
