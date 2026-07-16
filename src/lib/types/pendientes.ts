export interface PendingHistoryEntry {
    date: string;
    update: string;
}

export interface PendingRow {
    id: string;
    source_row: number;
    summary: Record<string, string>;
    latest_update: PendingHistoryEntry;
    history: PendingHistoryEntry[];
}

export interface PendingSourceData {
    source: 'emision-servicios' | 'siniestros';
    title: string;
    sheet_name: string;
    core_headers: string[];
    latest_update_header: string;
    rows: PendingRow[];
}
