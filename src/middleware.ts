import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

function sameOriginRedirect(request: NextRequest, path: string) {
    const forwardedHost = request.headers.get('x-forwarded-host')
        ?.split(',')[0]
        .trim()
        .toLowerCase();
    const host = forwardedHost || request.headers.get('host')?.toLowerCase();
    const publicHosts = new Set(['taiico-crm.com', 'www.taiico-crm.com']);
    const origin = host && publicHosts.has(host)
        ? `https://${host}`
        : request.nextUrl.origin;

    return NextResponse.redirect(new URL(path, origin));
}

export function middleware(request: NextRequest) {
    const path = request.nextUrl.pathname;

    // Define public paths that don't require authentication
    const isPublicPath = path === '/login' || path.startsWith('/_next') || path.startsWith('/static') || path === '/logo.png';

    const token = request.cookies.get('taiico_session')?.value;

    if (isPublicPath) {
        return NextResponse.next();
    }

    // If no token and trying to access protected route, redirect to login
    if (!token) {
        return sameOriginRedirect(request, '/login');
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
};
