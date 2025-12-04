export function parseExcelDate(value: number | string): Date | null {
    if (!value) return null;

    if (typeof value === 'number') {
        // Excel date serial number
        // Excel base date is Dec 30, 1899
        const date = new Date(Math.round((value - 25569) * 86400 * 1000));
        return date;
    }

    if (typeof value === 'string') {
        // Try parsing string formats like "DD/MM/YYYY" or "YYYY-MM-DD"
        // Assuming DD/MM/YYYY for Spanish locale usually
        const parts = value.split('/');
        if (parts.length === 3) {
            const day = parseInt(parts[0], 10);
            const month = parseInt(parts[1], 10) - 1;
            const year = parseInt(parts[2], 10);
            return new Date(year, month, day);
        }
        const date = new Date(value);
        if (!isNaN(date.getTime())) return date;
    }

    return null;
}

export function isUpcoming(date: Date, days: number): boolean {
    const now = new Date();
    const future = new Date();
    future.setDate(now.getDate() + days);
    return date >= now && date <= future;
}
