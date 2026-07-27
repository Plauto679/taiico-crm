export interface PendingHistoryEntry {
    date: string;
    update: string;
}

export interface PendingRow {
    id: string;
    source_row: number;
    summary: Record<string, string>;
    latest_update: PendingHistoryEntry;
    history: PendingHistoryEntry[];
    folder_name?: string;
    folder_id?: string | null;
    folder_url?: string | null;
}

export interface PendingSourceData {
    source: 'emision-servicios' | 'siniestros';
    title: string;
    sheet_name: string;
    core_headers: string[];
    latest_update_header: string;
    rows: PendingRow[];
}

export interface EmisionServiciosPendingInput {
    asegurado: string;
    rfc: string;
    poliza: string;
    casificacion: 'Vida' | 'GMM';
    tipo_tramite: 'Servicios' | 'Emisión';
    solicitud_de: string;
}

export interface SiniestrosPendingInput {
    asegurado: string;
    rfc: string;
    tipo_tramite: 'Cirugía Progamada' | 'Reembolso' | 'Programación de Medicamentos' | 'Programación de estudios/terapias';
    tramite: 'Complemento' | 'Reconsideración' | 'Garantías';
}

export interface PendingCreateResponse {
    created: boolean;
    row: PendingRow;
    folder_warning?: string | null;
}

export interface PendingFollowUpResponse {
    updated: boolean;
    date_header: string;
    row: PendingRow;
}

export interface PendingUpdateResponse {
    updated: boolean;
    row: PendingRow;
    folder_warning?: string | null;
}

export interface PendingDocument {
    id: string;
    name: string;
    mimeType?: string;
    webViewLink?: string;
    modifiedTime?: string;
    size?: string;
}

export interface PendingDocumentsResponse {
    row: PendingRow;
    folder_missing: boolean;
    required_documents: string[];
    documents: PendingDocument[];
}

export interface PendingReportSendResponse {
    sent: boolean;
    recipient: string;
    recipients: string[];
    generated_on: string;
}
