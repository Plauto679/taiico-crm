import { NextRequest } from 'next/server';


export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const FASTAPI_URL = `${process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777'}/renovaciones/send-email`;

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
        const contentType = response.headers.get('content-type') || 'application/json';
        return new Response(await response.text(), {
            status: response.status,
            headers: {
                'Content-Type': contentType,
                'X-Taiico-Route': 'renewal-email',
            },
        });
    } catch (error) {
        const detail = error instanceof Error && error.name === 'TimeoutError'
            ? 'El envío superó 120 segundos. Revisa el correo antes de volver a intentarlo.'
            : 'No fue posible conectar con el servicio de correo.';
        return Response.json(
            { detail },
            { status: 504, headers: { 'X-Taiico-Route': 'renewal-email' } },
        );
    }
}
