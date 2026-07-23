import { NextRequest } from 'next/server';


export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const FASTAPI_URL = `${process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777'}/pendientes/report`;

export async function POST(request: NextRequest) {
    try {
        const response = await fetch(FASTAPI_URL, {
            method: 'POST',
            headers: {
                'Content-Type': request.headers.get('content-type') || 'application/json',
                Cookie: request.headers.get('cookie') || '',
            },
            body: await request.text(),
            cache: 'no-store',
            signal: AbortSignal.timeout(120_000),
        });
        return new Response(await response.text(), {
            status: response.status,
            headers: {
                'Content-Type': response.headers.get('content-type') || 'application/json',
                'X-Taiico-Route': 'pending-report',
            },
        });
    } catch (error) {
        const detail = error instanceof Error && error.name === 'TimeoutError'
            ? 'La preparación y envío del informe superó 120 segundos.'
            : 'No fue posible conectar con el servicio del informe.';
        return Response.json(
            { detail },
            { status: 504, headers: { 'X-Taiico-Route': 'pending-report' } },
        );
    }
}
