import { fetchFromApi } from '@/lib/api';

export type CommissionPeriod = { id: string; month: string; status: string; currency: string; utility_coefficient: number; vat_rate: number; opening_balance: number; batch_count: number; exception_count: number };
export type CommissionWorkspace = { periods: CommissionPeriod[]; summary: { periods: number; prospectors: number; pending_exceptions: number; fixed_coefficient: number } };
export type CommissionBatch = { id: string; source: string; filename: string; status: string; raw_rows: number; consolidated_rows: number; exceptions: number; created_at: string | null };
export type CommissionException = { id: string; batch_id: string; policy_number: string; receipt_number: string; insurer_id: string; branch: string; movement_date: string | null; source_commission: number; currency: string; reason: string };
export type CommissionPeriodDetail = { period: CommissionPeriod; batches: CommissionBatch[]; exceptions: CommissionException[] };
export type ImportPreview = {
  token: string;
  source: string;
  filename: string;
  summary: { raw_rows: number; consolidated_rows: number; ready_rows: number; exception_rows: number; source_commission: number; prospector_total: number; workbook_issues: Array<{ issue_summary: string }> };
  sample: Array<{ policy_number: string; receipt_number: string; branch: string; source_commission: string; status: string; exception_reason?: string | null; allocations: Array<{ prospector_name: string; commission_rate: string; calculation: { total_amount: string } }> }>;
};

export const getProspectorCommissionWorkspace = () => fetchFromApi<CommissionWorkspace>('/cobranza-prospectadores');
export const createCommissionPeriod = (month: string) => fetchFromApi<{ period: CommissionPeriod }>('/cobranza-prospectadores/periods', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ month, currency: 'MXN' }),
});
export const getCommissionPeriodDetail = (periodId: string) => fetchFromApi<CommissionPeriodDetail>(`/cobranza-prospectadores/periods/${periodId}`);
export const previewCommissionImport = (periodId: string, source: string, file: File) => {
  const body = new FormData();
  body.append('period_id', periodId);
  body.append('source', source);
  body.append('file', file);
  return fetchFromApi<ImportPreview>('/cobranza-prospectadores/imports/preview', { method: 'POST', body });
};
export const applyCommissionImport = (token: string) => fetchFromApi<{ batch_id: string; status: string; consolidated_rows: number; exception_count: number; allocation_count: number }>(`/cobranza-prospectadores/imports/${token}/apply`, { method: 'POST' });
