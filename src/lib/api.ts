const API_BASE_URL = 'http://localhost:7777';

export async function fetchFromApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        cache: 'no-store', // Ensure fresh data
        ...options
    });

    if (!response.ok) {
        // Try to get error message from body
        let errorMessage = response.statusText;
        try {
            const errorBody = await response.json();
            if (errorBody.detail) {
                errorMessage = typeof errorBody.detail === 'string' ? errorBody.detail : JSON.stringify(errorBody.detail);
            }
        } catch (e) {
            // Ignore if body is not json
        }
        throw new Error(`API Error: ${errorMessage}`);
    }

    return response.json();
}
