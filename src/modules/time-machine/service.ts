import { fetchFromApi } from '@/lib/api';

export interface RestorePoint {
    id: string;
    name: string;
    backup_date: string;
    created_time?: string | null;
    size: number;
    web_view_link?: string | null;
    reason: 'daily' | 'pre_restore' | string;
}

export interface BackupSource {
    key: string;
    name: string;
    versions: RestorePoint[];
    version_count: number;
    latest_backup_date?: string | null;
}

export interface TimeMachineCatalog {
    root_folder_url: string;
    sources: BackupSource[];
    can_restore: boolean;
}

export function getTimeMachineCatalog(): Promise<TimeMachineCatalog> {
    return fetchFromApi('/time-machine');
}

export function restoreTimeMachineBackup(input: {
    source_key: string;
    backup_file_id: string;
    confirmation: string;
}): Promise<{
    success: boolean;
    source_name: string;
    restored_backup: { id: string; name: string };
    safety_backup: { id: string; name: string; webViewLink?: string };
}> {
    return fetchFromApi('/time-machine/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}
