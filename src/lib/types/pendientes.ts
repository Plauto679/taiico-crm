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
    access: PendingAccess;
    inconsistencies: PendingAssignmentInconsistency[];
}

export interface PendingAccess {
    role: string;
    can_operate: boolean;
    promotorias: string[];
    rfc: string;
    central_admin: boolean;
    agents: PendingAgentOption[];
    admins: PendingAdminOption[];
}

export interface PendingAdminOption {
    email: string;
    label: string;
}

export interface PendingAgentOption {
    rfc: string;
    name: string;
    promotoria: string;
    label: string;
}

export interface PendingAssignmentInconsistency {
    source: string;
    source_row: number;
    asegurado: string;
    poliza: string;
    promotoria: string;
    rfc_agente: string;
    problems: string[];
    action: string;
}

export interface PendingClientOption {
    id: string;
    nombre: string;
    rfc: string;
    estado_identidad: 'prospect' | 'identified' | string;
    expediente_url: string;
}

export interface EmisionServiciosPendingInput {
    request_id: string;
    client_id: string;
    asegurado: string;
    insured_name: string;
    rfc: string;
    poliza: string;
    casificacion: 'Vida' | 'GMM';
    tipo_tramite: 'Servicios' | 'Emisión';
    solicitud_de: string;
    promotoria: string;
    rfc_agente: string;
    responsable: string;
    recordatorio_futuro: string;
}

export interface SiniestrosPendingInput {
    request_id: string;
    client_id: string;
    asegurado: string;
    insured_name: string;
    rfc: string;
    poliza: string;
    tipo_tramite: 'Cirugía Progamada' | 'Reembolso' | 'Programación de Medicamentos' | 'Programación de estudios/terapias';
    tramite: 'Complemento' | 'Reconsideración' | 'Garantías';
    estatus: 'En Proceso' | 'Pagado' | 'Rechazado' | 'Suspendido';
    promotoria: string;
    rfc_agente: string;
    responsable: string;
    recordatorio_futuro: string;
}

export interface PendingCreateResponse {
    created: boolean;
    row: PendingRow;
    folder_warning?: string | null;
    notification_warning?: string | null;
    notification_queued?: boolean;
    deduplicated?: boolean;
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

export interface PendingDeleteResponse {
    deleted: boolean;
    source_row: number;
    folder_preserved: boolean;
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
