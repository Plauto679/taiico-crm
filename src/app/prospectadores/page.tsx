import { ProspectadoresView } from '@/components/prospectadores/ProspectadoresView';
import { getProspectors, getProspectorSummary, getProspectorMigrationPreview } from '@/modules/prospectadores/service';

export const dynamic = 'force-dynamic';

export default async function ProspectadoresPage() {
  const [list, summary, migration] = await Promise.all([
    getProspectors(), getProspectorSummary(), getProspectorMigrationPreview(),
  ]);
  return <ProspectadoresView initialProspectors={list.prospectors} initialSummary={summary} migration={migration} />;
}
