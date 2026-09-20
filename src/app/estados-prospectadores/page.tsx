import { getStatementWorkspace } from '@/modules/estados-prospectadores/service';
import { ProspectorStatementsView } from '@/components/estados-prospectadores/ProspectorStatementsView';
export const dynamic = 'force-dynamic';
export default async function Page() { return <ProspectorStatementsView initial={await getStatementWorkspace()} />; }
