import { LogsView } from '@/components/logs/LogsView';
import { getAuditLogs } from '@/modules/logs/service';

export const dynamic = 'force-dynamic';

export default async function LogsPage() {
  const response = await getAuditLogs();
  return <LogsView initialLogs={response.logs} driveFolderUrl={response.drive_folder_url} />;
}
