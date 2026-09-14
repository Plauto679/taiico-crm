import { FinanceView } from '@/components/finanzas/FinanceView';
import { getFinanceCategories, getFinanceOverview } from '@/modules/finanzas/service';

export const dynamic = 'force-dynamic';

export default async function FinancePage() {
  const [overview, categories] = await Promise.all([getFinanceOverview(), getFinanceCategories()]);
  return <FinanceView initialOverview={overview} categories={categories} />;
}
