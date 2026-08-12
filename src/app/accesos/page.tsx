import { AccesosView } from '@/components/accesos/AccesosView';
import { getAccessConfig, getAccessUsers } from '@/modules/accesos/service';

export const dynamic = 'force-dynamic';

export default async function AccesosPage() {
    const [config, usersResponse] = await Promise.all([
        getAccessConfig(),
        getAccessUsers(),
    ]);

    return (
        <div className="flex h-full min-h-0 flex-col p-8">
            <AccesosView
                initialUsers={usersResponse.users}
                modules={config.modules}
                promotorias={config.promotorias}
            />
        </div>
    );
}
