import { fetchFromApi } from '@/lib/api';
import {
    ReclutaCreateInput,
    ReclutaCreateResponse,
    ReclutaDocumentsResponse,
    ReclutaProspect,
    ReclutaSource,
    ReclutaUploadResponse,
} from '@/lib/types/recluta';


export async function getReclutaProspects(): Promise<ReclutaSource> {
    return fetchFromApi('/recluta/prospects');
}

export async function getReclutaDocuments(prospectId: string): Promise<ReclutaDocumentsResponse> {
    return fetchFromApi(`/recluta/prospects/${encodeURIComponent(prospectId)}/documents`);
}

export async function addReclutaProspect(input: ReclutaCreateInput): Promise<ReclutaCreateResponse> {
    return fetchFromApi('/recluta/prospects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}

export async function createReclutaFolder(
    prospectId: string,
): Promise<{ created: boolean; prospect: ReclutaProspect }> {
    return fetchFromApi(`/recluta/prospects/${encodeURIComponent(prospectId)}/folder`, {
        method: 'POST',
    });
}

export async function uploadReclutaDocument(
    prospectId: string,
    documentName: string,
    document: File,
): Promise<ReclutaUploadResponse> {
    const body = new FormData();
    body.append('document_name', documentName);
    body.append('document', document);
    return fetchFromApi(`/recluta/prospects/${encodeURIComponent(prospectId)}/documents`, {
        method: 'POST',
        body,
    });
}
