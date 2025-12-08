import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const path = request.nextUrl.pathname;

    // Define public paths that don't require authentication
    const isPublicPath = path === '/login' || path.startsWith('/_next') || path.startsWith('/static') || path === '/logo.png';

    const token = request.cookies.get('auth_token')?.value;

    if (isPublicPath) {
        // If user is already logged in and tries to access login page, redirect to dashboard
        if (path === '/login' && token) {
            return NextResponse.redirect(new URL('/', request.url));
        }
        return NextResponse.next();
    }

    // If no token and trying to access protected route, redirect to login
    if (!token) {
        return NextResponse.redirect(new URL('/login', request.url));
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
