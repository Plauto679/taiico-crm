import { fetchFromApi } from '@/lib/api';
export type Statement = {
  id: string; period_id: string; prospector_id: string; name: string; month: string; currency: string;
  prospector_active: boolean;
  status: 'pendiente' | 'enviado' | 'pagado'; recipient: string; commission: string;
  adjustment_total: string; carry_total: string; own_amount: string; total: string; revision: number;
  delivery_state: string; delivery_error: string | null; sent_at: string | null; paid_at: string | null;
};
export type StatementDetail = Statement & {
  lines: { policy: string; date: string; insurer: string; branch: string; rate: string | null; manual?: boolean; id?: string; commission: string; vat: string; total: string }[];
  adjustments: { concept: string; amount: string }[]; carry: { id: string; month: string; amount: string; vat?: string }[];
  notes: string; history: { at: string; actor: string; action: string }[];
};
export type StatementWorkspace = { periods: { id: string; month: string }[]; statements: Statement[]; prospectors: { id: string; name: string }[] };
export const getStatementWorkspace = () => fetchFromApi<StatementWorkspace>('/estados-prospectadores');
export const getStatement = (id: string) => fetchFromApi<StatementDetail>(`/estados-prospectadores/${id}`);
export const statementAction = <T,>(path: string, body: unknown, method = 'POST') => fetchFromApi<T>(`/estados-prospectadores/${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export async function downloadStatement(id: string, format: 'pdf' | 'xlsx') {
  const res = await fetch(`/api/estados-prospectadores/${id}/download/${format}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('No se pudo descargar el estado de cuenta.');
  const url = URL.createObjectURL(await res.blob()); const a = document.createElement('a');
  a.href = url; a.download = `estado-${id.slice(0,8)}.${format}`; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
