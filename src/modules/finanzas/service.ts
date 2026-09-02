import { fetchFromApi } from '@/lib/api';

export type Company = 'CONSOLIDADO' | 'TLA' | 'TS';
export type FinanceFilters = { bank?: string; startDate?: string; endDate?: string };
export type FinanceSource = { key: string; company: string; bank: string; available: boolean; row_count: number; last_modified_at: string | null; last_synced_at: string | null; error?: string | null };
export type MonthlyPoint = { month: string; entries: number; exits: number; net: number };
export type FinanceOverview = {
  company: Company; as_of: string;
  kpis: { active_cash: number; credit_liability: number; net_flow_month: number; entries_month: number; exits_month: number; unclassified: number; recurring_pending: number; invoice_gaps: number; tax_month: number; future_commitments: number };
  monthly: MonthlyPoint[]; sources: FinanceSource[];
};
export type FinanceMovement = { id: string; id_movimiento: string; empresa: string; banco: string; tipo_cuenta?: string; naturaleza_cuenta?: string; moneda: string; fecha_operacion: string; fecha_liquidacion?: string | null; descripcion_original: string; referencia?: string; contraparte?: string; cargo: number; abono: number; importe_neto: number; saldo?: number | null; categoria: string; subcategoria: string; recurrente: boolean; impuesto: boolean; nomina: boolean; requiere_factura: boolean; factura_uuid?: string; estatus_conciliacion_factura?: string; estatus_revision?: string; periodo_estado?: string; archivo_fuente?: string; pagina_fuente?: number | null };
export type MovementResponse = { items: FinanceMovement[]; total: number; page: number; page_size: number; categories: string[] };
export type RecurringGroup = { fingerprint: string; company: string; label: string; occurrences: number; months: number; average_amount: number; last_date: string; status: string; note?: string | null; basis: string };
export type FinanceInvoice = { id: string; filename: string; file_type: string; uuid?: string | null; issuer_rfc?: string | null; receiver_rfc?: string | null; issued_at?: string | null; total?: number | null; currency?: string | null; status: string; parse_error?: string | null };
export type Projection = { id: string; company: string; due_date: string; concept: string; amount: number; scenario: string; status: string; source: string };
export type Rule = { id: string; name: string; priority: number; field: string; operator: string; value: string; company?: string | null; category: string; subcategory?: string | null; enabled: boolean; exclusion: boolean; updated_at: string };
export type Budget = { id: string; company: string; month: string; category: string; budget: number; actual: number; variance: number };

function financeQuery(company: Company, filters: FinanceFilters = {}, extra: Record<string, string | number> = {}) {
  const params = new URLSearchParams({ company });
  if (filters.bank) params.set('bank', filters.bank);
  if (filters.startDate) params.set('start_date', filters.startDate);
  if (filters.endDate) params.set('end_date', filters.endDate);
  Object.entries(extra).forEach(([key, value]) => params.set(key, String(value)));
  return params.toString();
}

export const getFinanceOverview = (company: Company = 'CONSOLIDADO', filters: FinanceFilters = {}) => fetchFromApi<FinanceOverview>(`/finanzas/overview?${financeQuery(company, filters)}`);
export const getMovements = (company: Company, search = '', filters: FinanceFilters = {}) => fetchFromApi<MovementResponse>(`/finanzas/movements?${financeQuery(company, filters, { search, page: 1, page_size: 5000 })}`);
export const updateMovement = (id: string, payload: Record<string, unknown>) => fetchFromApi<{ movement: FinanceMovement }>(`/finanzas/movements/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
export async function exportMovements(company: Company, search = '', filters: FinanceFilters = {}) {
  const response = await fetch(`/api/finanzas/movements/export?${financeQuery(company, filters, { search })}`, { credentials: 'same-origin' });
  if (!response.ok) throw new Error('No se pudo exportar el archivo de Excel');
  const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
  const disposition = response.headers.get('Content-Disposition');
  const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] || `movimientos-${company.toLowerCase()}.xlsx`;
  anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}
export const getRecurring = (company: Company, filters: FinanceFilters = {}) => fetchFromApi<{ items: RecurringGroup[] }>(`/finanzas/recurring?${financeQuery(company, filters)}`);
export const decideRecurring = (fingerprint: string, status: string) => fetchFromApi(`/finanzas/recurring/${fingerprint}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
export const getInvoices = () => fetchFromApi<{ items: FinanceInvoice[]; folder_available: boolean }>('/finanzas/invoices');
export const scanInvoices = () => fetchFromApi<{ available: boolean; indexed: number; errors: number; message?: string }>('/finanzas/invoices/scan', { method: 'POST' });
export const getInvoiceSuggestions = (id: string) => fetchFromApi<{ items: Array<{ movement: FinanceMovement; confidence: number; rationale: string }>; reason: string }>(`/finanzas/invoices/${id}/suggestions`);
export const matchInvoice = (invoiceId: string, movementId: string) => fetchFromApi(`/finanzas/invoices/${invoiceId}/match`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ movement_id: movementId, status: 'confirmado' }) });
export const getCashFlow = (company: Company, scenario = 'base') => fetchFromApi<{ items: Projection[]; total: number }>(`/finanzas/cash-flow?company=${company}&scenario=${scenario}`);
export const createProjection = (payload: Omit<Projection, 'id' | 'status' | 'source'>) => fetchFromApi<{ projection: Projection }>('/finanzas/projections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
export const cancelProjection = (id: string) => fetchFromApi(`/finanzas/projections/${id}`, { method: 'DELETE' });
export const getBudgets = (company: Company) => fetchFromApi<{ items: Budget[]; budget: number; actual: number }>(`/finanzas/budgets?company=${company}`);
export const upsertBudget = (payload: { company: 'TLA' | 'TS'; month: string; category: string; amount: number }) => fetchFromApi('/finanzas/budgets', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
export const getRules = () => fetchFromApi<{ items: Rule[] }>('/finanzas/rules');
export const createRule = (payload: Omit<Rule, 'id' | 'updated_at'>) => fetchFromApi<{ rule: Rule }>('/finanzas/rules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
export const deleteRule = (id: string) => fetchFromApi(`/finanzas/rules/${id}`, { method: 'DELETE' });
export const previewRule = (id: string) => fetchFromApi<{ total: number; conflicts: number; sample: FinanceMovement[] }>(`/finanzas/rules/${id}/preview`, { method: 'POST' });
export const applyRule = (id: string) => fetchFromApi<{ updated: number }>(`/finanzas/rules/${id}/apply`, { method: 'POST' });
export const revertRule = (id: string) => fetchFromApi<{ restored: number }>(`/finanzas/rules/${id}/revert`, { method: 'POST' });
export const syncSources = () => fetchFromApi<{ sources: FinanceSource[] }>('/finanzas/sources/sync', { method: 'POST' });
export async function previewIngestion(sourceKey: string, file: File) {
  const data = new FormData(); data.set('file', file);
  return fetchFromApi<{ ingestion_id: string; rows: number; new_rows: number; duplicates: number; sample: Array<Record<string, unknown>> }>(`/finanzas/ingestions/preview?source_key=${sourceKey}`, { method: 'POST', body: data });
}
export const publishIngestion = (id: string) => fetchFromApi<{ success: boolean; published_rows: number; backup_created: boolean }>(`/finanzas/ingestions/${id}/publish`, { method: 'POST' });
