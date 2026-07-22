import { fetchFromApi } from '@/lib/api';
import {
    EmisionServiciosPendingInput,
    PendingCreateResponse,
    PendingDocument,
    PendingDocumentsResponse,
    PendingSourceData,
    SiniestrosPendingInput,
} from '@/lib/types/pendientes';

export function getPendingSource(
    source: 'emision-servicios' | 'siniestros',
): Promise<PendingSourceData> {
    return fetchFromApi<PendingSourceData>(`/pendientes/${source}`);
}

export function getPendingDocuments(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
): Promise<PendingDocumentsResponse> {
    return fetchFromApi(`/pendientes/${source}/${sourceRow}/documents`);
}

export function createPendingFolder(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
): Promise<{ created: boolean; row: PendingDocumentsResponse['row'] }> {
    return fetchFromApi(`/pendientes/${source}/${sourceRow}/folder`, { method: 'POST' });
}

export function uploadPendingDocument(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
    documentName: string,
    document: File,
): Promise<{ uploaded: boolean; document: PendingDocument }> {
    const body = new FormData();
    body.append('document_name', documentName);
    body.append('document', document);
    return fetchFromApi(`/pendientes/${source}/${sourceRow}/documents`, {
        method: 'POST',
        body,
    });
}

export function createEmisionServiciosPending(
    input: EmisionServiciosPendingInput,
): Promise<PendingCreateResponse> {
    return fetchFromApi('/pendientes/emision-servicios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}

export function createSiniestrosPending(
    input: SiniestrosPendingInput,
): Promise<PendingCreateResponse> {
    return fetchFromApi('/pendientes/siniestros', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}
