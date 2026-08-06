import { NextRequest } from 'next/server';


export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

const FASTAPI_URL = `${process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777'}/base-loads/metlife-gmm/preview`;
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

export async function POST(request: NextRequest) {
    try {
        const declaredLength = Number(request.headers.get('content-length') || 0);
        if (declaredLength > MAX_UPLOAD_BYTES) {
            return Response.json(
                { detail: 'El archivo excede el límite de 100 MB.' },
                { status: 413, headers: { 'X-Taiico-Route': 'base-load-preview' } },
            );
        }

        // Buffer this single, size-limited upload before forwarding it. Passing the
        // incoming web stream directly to undici resets the connection for larger
        // multipart requests under Next.js, before FastAPI can return its response.
        const body = await request.arrayBuffer();
        if (body.byteLength > MAX_UPLOAD_BYTES) {
            return Response.json(
                { detail: 'El archivo excede el límite de 100 MB.' },
                { status: 413, headers: { 'X-Taiico-Route': 'base-load-preview' } },
            );
        }

        const headers = new Headers();
        for (const name of ['content-type', 'cookie']) {
            const value = request.headers.get(name);
            if (value) headers.set(name, value);
        }
        headers.set('content-length', String(body.byteLength));

        const response = await fetch(FASTAPI_URL, {
            method: 'POST',
            headers,
            body,
            cache: 'no-store',
            signal: AbortSignal.timeout(300_000),
        });

        const responseHeaders = new Headers({
            'Content-Type': response.headers.get('content-type') || 'application/json',
            'X-Taiico-Route': 'base-load-preview',
        });

        return new Response(response.body, {
            status: response.status,
            headers: responseHeaders,
        });
    } catch (error) {
        console.error('Base load preview proxy failed', error);
        const timedOut = error instanceof Error
            && (error.name === 'TimeoutError' || error.name === 'AbortError');
        return Response.json(
            {
                detail: timedOut
                    ? 'La preparación de la vista previa superó 5 minutos.'
                    : 'No fue posible transmitir el archivo al servicio de carga.',
            },
            {
                status: timedOut ? 504 : 502,
                headers: { 'X-Taiico-Route': 'base-load-preview' },
            },
        );
    }
}
