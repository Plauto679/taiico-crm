const API_BASE_URL = 'http://localhost:7777';

export async function fetchFromApi<T>(endpoint: string, params: Record<string, string | number> = {}): Promise<T> {
    const url = new URL(`${API_BASE_URL}${endpoint}`);
    Object.keys(params).forEach(key => url.searchParams.append(key, String(params[key])));

    const response = await fetch(url.toString(), {
        cache: 'no-store', // Ensure fresh data
    });

    if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
}
