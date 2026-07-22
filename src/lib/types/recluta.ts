export interface ReclutaProspect {
    id: string;
    source_row: number;
    nombre: string;
    telefono: string;
    correo: string;
    rfc: string;
    fase: string;
    estatus: string;
    raw: Record<string, string>;
    folder_name: string;
    folder_id: string | null;
    folder_url: string | null;
}

export interface ReclutaSource {
    source_file_id: string;
    source_url: string;
    documents_folder_id: string;
    documents_folder_url: string;
    columns: string[];
    phases: string[];
    prospects: ReclutaProspect[];
}

export interface ReclutaDocument {
    id: string;
    name: string;
    mimeType: string;
    webViewLink?: string;
    modifiedTime?: string;
    size?: string;
}

export interface ReclutaDocumentsResponse {
    prospect: ReclutaProspect;
    folder_missing: boolean;
    documents: ReclutaDocument[];
}

export interface ReclutaCreateInput {
    nombre: string;
    telefono: string;
    correo: string;
    rfc: string;
    fase: string;
    estatus: string;
}

export interface ReclutaCreateResponse {
    created: boolean;
    prospect: ReclutaProspect;
    folder_warning: string | null;
}

export interface ReclutaUploadResponse {
    uploaded: boolean;
    document: ReclutaDocument;
}
