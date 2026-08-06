import { NextRequest } from 'next/server';


export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 600;

const API_BASE_URL = process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777';

export async function POST(
    request: NextRequest,
    { params }: { params: Promise<{ token: string }> },
) {
    const { token } = await params;
    const backendUrl = `${API_BASE_URL}/base-loads/metlife-gmm/apply/${encodeURIComponent(token)}`;
    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: {
                Cookie: request.headers.get('cookie') || '',
            },
            cache: 'no-store',
            signal: AbortSignal.timeout(600_000),
        });
        return new Response(await response.text(), {
            status: response.status,
            headers: {
                'Content-Type': response.headers.get('content-type') || 'application/json',
                'X-Taiico-Route': 'base-load-apply',
            },
        });
    } catch (error) {
        console.error('Base load apply proxy failed', error);
        const timedOut = error instanceof Error
            && (error.name === 'TimeoutError' || error.name === 'AbortError');
        const reason = error instanceof Error ? error.message : String(error);
        return Response.json(
            {
                detail: timedOut
                    ? 'La aplicación superó 10 minutos. El archivo preparado se conservó para reintentar.'
                    : `No fue posible conectar con el servicio de carga: ${reason}`,
            },
            {
                status: timedOut ? 504 : 502,
                headers: { 'X-Taiico-Route': 'base-load-apply' },
            },
        );
    }
}
