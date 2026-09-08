import { TimeMachineView } from '@/components/time-machine/TimeMachineView';
import { getTimeMachineCatalog } from '@/modules/time-machine/service';

export const dynamic = 'force-dynamic';

export default async function TimeMachinePage() {
    const catalog = await getTimeMachineCatalog();
    return <TimeMachineView initialCatalog={catalog} />;
}
