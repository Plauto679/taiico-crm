import { AgentsView } from '@/components/agentes/AgentsView';
import { getAgents } from '@/modules/agentes/service';

export default async function AgentsPage() {
  const directory = await getAgents();
  return <AgentsView initialDirectory={directory} />;
}
