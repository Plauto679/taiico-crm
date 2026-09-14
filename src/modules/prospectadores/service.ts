import { fetchFromApi } from '@/lib/api';

export type Prospector = {
  id: string; name: string; rfc: string; email: string; additional_emails: string[];
  payment_scheme: 'factura' | 'asimilados_salarios'; invoice_required: boolean;
  is_active: boolean; linked_username: string; assignment_count: number;
};

export type ProspectorSummary = { total: number; active: number; with_assignments: number; active_assignments: number };
export type MigrationPreview = { policies_with_prospector: number; policies_pending: number; unique_prospectors: number; split_policies: number };

export const getProspectors = () => fetchFromApi<{ prospectors: Prospector[] }>('/prospectadores');
export const getProspectorSummary = () => fetchFromApi<ProspectorSummary>('/prospectadores/summary');
export const getProspectorMigrationPreview = () => fetchFromApi<MigrationPreview>('/prospectadores/migration-preview');

export type ProspectorInput = Omit<Prospector, 'id' | 'invoice_required' | 'assignment_count'>;
export const createProspector = (payload: ProspectorInput) => fetchFromApi<{ prospector: Prospector }>('/prospectadores', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
});
export const updateProspector = (id: string, payload: ProspectorInput) => fetchFromApi<{ prospector: Prospector }>(`/prospectadores/${id}`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
});
export const mergeProspector = (sourceId: string, targetId: string) => fetchFromApi<{ target_id: string; target_name: string; removed_source_id: string; moved_assignments: number; moved_balances: number }>(`/prospectadores/${sourceId}/merge`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_id: targetId }),
});
export const migrateCarteraProspectors = () => fetchFromApi<{ created_prospectors: number; created_assignments: number; skipped: number }>('/prospectadores/migrate-cartera', { method: 'POST' });
