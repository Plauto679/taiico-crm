import { LeadInbox } from '@/components/captacion/LeadInbox';
import { fetchFromApi } from '@/lib/api';
import type { LeadInboxData } from '@/components/captacion/LeadInbox';
export const dynamic = 'force-dynamic';
export default async function CaptacionPage({ searchParams }: { searchParams: Promise<{ tipo?: string }> }) {
  const params = await searchParams;
  const kind = params.tipo === 'agentes' ? 'agentes' : 'clientes';
  const data = await fetchFromApi<LeadInboxData>(`/captacion/leads/${kind}`);
  return <LeadInbox key={kind} kind={kind} initial={data} />;
}
