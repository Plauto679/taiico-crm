import { AutomaticMailsView } from '@/components/automatic-mails/AutomaticMailsView';
import { getAutomaticMails } from '@/modules/automatic-mails/service';

export const dynamic = 'force-dynamic';

export default async function AutomaticMailsPage() {
  const directory = await getAutomaticMails();
  return <AutomaticMailsView initialDirectory={directory} />;
}
