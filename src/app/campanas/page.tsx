import { CampaignsView } from '@/components/campanas/CampaignsView';
import { getCampaigns } from '@/modules/campanas/service';

export const dynamic = 'force-dynamic';

export default async function CampaignsPage() {
  const data = await getCampaigns();
  return <CampaignsView initialCampaigns={data.campaigns} safeVariables={data.safe_variables} />;
}
