import { fetchFromApi } from '@/lib/api';
import {
    EmisionServiciosPendingInput,
    PendingCreateResponse,
    PendingDocument,
    PendingDeleteResponse,
    PendingDocumentsResponse,
    PendingFollowUpResponse,
    PendingReportSendResponse,
    PendingSourceData,
    PendingUpdateResponse,
    SiniestrosPendingInput,
} from '@/lib/types/pendientes';

export function sendPendingReport(emails: string[]): Promise<PendingReportSendResponse> {
    return fetchFromApi('/pendientes/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emails }),
    });
}

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

export function createPendingFollowUp(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
    comment: string,
): Promise<PendingFollowUpResponse> {
    return fetchFromApi(`/pendientes/${source}/${sourceRow}/follow-up`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment }),
    });
}

export function updatePendingRecord(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
    values: Record<string, string>,
): Promise<PendingUpdateResponse> {
    return fetchFromApi(`/pendientes/${source}/${sourceRow}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
    });
}

export function deletePendingRecord(
    source: 'emision-servicios' | 'siniestros',
    sourceRow: number,
): Promise<PendingDeleteResponse> {
    return fetchFromApi(`/pendientes/${source}/${sourceRow}`, {
        method: 'DELETE',
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
