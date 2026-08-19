export interface Cliente {
    id?: string | null;
    nombre: string;
    rfc?: string | null;
    correo?: string | null;
    telefono?: string | null;
    estado_identidad?: 'prospect' | 'identified' | string;
    expediente_id?: string | null;
    expediente_url?: string | null;
    expediente_nombre?: string | null;
    expediente_verificado?: string | null;
}

export interface ClientRegistryAuditSummary {
    total_clients: number;
    prospects_without_rfc: number;
    identified_clients: number;
    invalid_client_rfcs: number;
    duplicate_client_rfcs: number;
    total_drive_folders: number;
    malformed_drive_folders: number;
    duplicate_drive_rfcs: number;
    linked_clients: number;
    safe_links_available: number;
    clients_missing_folder: number;
    unregistered_drive_folders: number;
    folder_name_mismatches: number;
}

export interface ClientRegistryAudit {
    summary: ClientRegistryAuditSummary;
    details: {
        duplicate_client_rfcs: Array<{ rfc: string; clients: Array<{ id: string; nombre: string }> }>;
        duplicate_drive_rfcs: Array<{ rfc: string; folders: Array<{ id: string; name: string; url: string }> }>;
        malformed_folders: Array<{ id: string; name: string; url: string }>;
    };
    truncated: Record<string, boolean>;
    drive_folder_url: string;
}
