// Browser requests stay on the same origin and are proxied by Next.js. Server
// Components call FastAPI directly because Node.js cannot parse relative URLs.
const API_BASE_URL = typeof window === 'undefined'
    ? (process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777')
    : '/api';

export async function fetchFromApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const requestHeaders = new Headers(options?.headers);

    if (typeof window === 'undefined') {
        const { cookies } = await import('next/headers');
        const cookieStore = await cookies();
        const cookieHeader = cookieStore
            .getAll()
            .map(({ name, value }) => `${name}=${value}`)
            .join('; ');
        if (cookieHeader) requestHeaders.set('Cookie', cookieHeader);
    }

    const response = await fetch(url, {
        cache: 'no-store', // Ensure fresh data
        ...options,
        headers: requestHeaders,
    });

    if (!response.ok) {
        // Try to get error message from body
        let errorMessage = response.statusText || `HTTP ${response.status}`;
        try {
            const errorBody = await response.json();
            if (errorBody.detail) {
                errorMessage = typeof errorBody.detail === 'string' ? errorBody.detail : JSON.stringify(errorBody.detail);
            }
        } catch {
            // Ignore if body is not json
        }
        throw new Error(`API Error: ${errorMessage}`);
    }

    return response.json();
}
