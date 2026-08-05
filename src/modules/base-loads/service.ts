import type { BaseLoadApplyResult, BaseLoadPreview } from '@/lib/types/baseLoads';

async function responseJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let detail = response.statusText || `HTTP ${response.status}`;
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch {
            // Preserve the HTTP status text when the backend did not return JSON.
        }
        throw new Error(detail);
    }
    return response.json() as Promise<T>;
}

export async function previewMetlifeGmmBase(file: File): Promise<BaseLoadPreview> {
    const body = new FormData();
    body.append('file', file);
    return responseJson<BaseLoadPreview>(await fetch('/api/base-loads/metlife-gmm/preview', {
        method: 'POST',
        body,
        credentials: 'same-origin',
        cache: 'no-store',
    }));
}

export async function applyMetlifeGmmBase(token: string): Promise<BaseLoadApplyResult> {
    return responseJson<BaseLoadApplyResult>(await fetch(`/api/base-loads/metlife-gmm/apply/${token}`, {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
    }));
}
