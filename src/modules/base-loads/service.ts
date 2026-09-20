import type { BaseLoadApplyResult, BaseLoadPreview } from '@/lib/types/baseLoads';

async function responseJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let detail = response.statusText || `HTTP ${response.status}`;
        try {
            const text = await response.text();
            if (text) {
                try {
                    const payload = JSON.parse(text);
                    detail = payload.detail || detail;
                } catch {
                    detail = response.status === 524 || response.status === 504
                        ? 'La conexión agotó el tiempo de espera. El archivo puede seguir procesándose; intenta consultar la vista previa nuevamente.'
                        : `No se pudo completar la solicitud (HTTP ${response.status}). Inténtalo nuevamente.`;
                }
            }
        } catch {
            // Preserve the HTTP status text when the response body is unavailable.
        }
        throw new Error(detail);
    }
    return response.json() as Promise<T>;
}

export async function previewMetlifeGmmBase(file: File): Promise<BaseLoadPreview> {
    const body = new FormData();
    body.append('file', file);
    const job = await responseJson<BaseLoadPreview | { token: string; status: 'processing' }>(await fetch('/api/base-loads/metlife-gmm/preview', {
        method: 'POST',
        body,
        credentials: 'same-origin',
        cache: 'no-store',
    }));
    if ('preview' in job) return job;
    // Each status request is short even when the workbook takes several minutes.
    for (let attempt = 0; attempt < 600; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const progress = await responseJson<{
            status: 'processing' | 'completed' | 'failed';
            result?: BaseLoadPreview;
            detail?: string;
        }>(await fetch(`/api/base-loads/metlife-gmm/preview/${job.token}`, {
            credentials: 'same-origin', cache: 'no-store',
        }));
        if (progress.status === 'completed' && progress.result) return progress.result;
        if (progress.status === 'failed') throw new Error(progress.detail || 'No se pudo preparar la vista previa.');
    }
    throw new Error('La preparación superó 20 minutos. Inténtalo nuevamente.');
}

export async function applyMetlifeGmmBase(token: string): Promise<BaseLoadApplyResult> {
    const job = await responseJson<BaseLoadApplyResult | { status: string; detail?: string }>(await fetch(`/api/base-loads/metlife-gmm/apply/${token}`, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
    }));
    if ('applied' in job) return job;
    if (job.status === 'failed') throw new Error(job.detail || 'No se pudo completar la actualización.');
    for (let attempt = 0; attempt < 600; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const progress = await responseJson<{
            status: string; result?: BaseLoadApplyResult; detail?: string;
        }>(await fetch(`/api/base-loads/metlife-gmm/apply/${token}`, {
            credentials: 'same-origin', cache: 'no-store',
        }));
        if (progress.status === 'completed' && progress.result) return progress.result;
        if (progress.status === 'failed') throw new Error(progress.detail || 'No se pudo completar la actualización.');
    }
    throw new Error('La actualización sigue en proceso. Pulsa Aplicar nuevamente para consultar su resultado; no se repetirá la carga.');
}

export async function previewMetlifeVidaBase(file: File): Promise<BaseLoadPreview> {
    const body = new FormData();
    body.append('file', file);
    return responseJson<BaseLoadPreview>(await fetch('/api/base-loads/metlife-vida/preview', {
        method: 'POST',
        body,
        credentials: 'same-origin',
        cache: 'no-store',
    }));
}

export async function applyMetlifeVidaBase(token: string): Promise<BaseLoadApplyResult> {
    return responseJson<BaseLoadApplyResult>(await fetch(`/api/base-loads/metlife-vida/apply/${token}`, {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
    }));
}
