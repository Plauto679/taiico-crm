import { fetchFromApi } from '@/lib/api';

export interface AuditLogEntry {
  id: string;
  occurred_at: string;
  username: string;
  module: string;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  http_method: string;
  endpoint: string;
  status_code: number;
  outcome: 'exitoso' | 'error';
  changes: Record<string, unknown>;
  ip_address?: string | null;
  user_agent?: string | null;
}

export interface AuditLogResponse {
  logs: AuditLogEntry[];
  drive_folder_url: string;
}

export async function getAuditLogs(): Promise<AuditLogResponse> {
  return fetchFromApi<AuditLogResponse>('/logs');
}

export async function syncAuditLogs(): Promise<{ success: boolean; url?: string; folder_url: string }> {
  return fetchFromApi('/logs/sync', { method: 'POST' });
}
