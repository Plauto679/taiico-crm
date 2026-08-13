import { RRHHView } from '@/components/rrhh/RRHHView';
import { getHrData } from '@/modules/rrhh/service';

export const dynamic = 'force-dynamic';

export default async function RRHHPage() {
  const data = await getHrData();
  return <RRHHView initialCollaborators={data.collaborators} initialVacations={data.vacations} sourceUrl={data.source_url} />;
}
