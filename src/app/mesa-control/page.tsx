import { fetchFromApi } from '@/lib/api';
import { redirect } from 'next/navigation';
import { MesaControlView } from '@/components/mesa-control/MesaControlView';

export default async function MesaControlPage() {
    const session = await fetchFromApi<{ mesa_access?: boolean }>('/session');
    if (!session.mesa_access) redirect('/sin-acceso');
    return <MesaControlView />;
}
