import { CobranzaProspectadoresView } from '@/components/cobranza-prospectadores/CobranzaProspectadoresView';
import { getProspectorCommissionWorkspace } from '@/modules/cobranza-prospectadores/service';

export const dynamic = 'force-dynamic';

export default async function CobranzaProspectadoresPage() {
  return <CobranzaProspectadoresView initialWorkspace={await getProspectorCommissionWorkspace()} />;
}
