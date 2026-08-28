import { FinanceView } from '@/components/finanzas/FinanceView';
import { getFinanceOverview } from '@/modules/finanzas/service';

export const dynamic = 'force-dynamic';

export default async function FinancePage() {
  const overview = await getFinanceOverview();
  return <FinanceView initialOverview={overview} />;
}
