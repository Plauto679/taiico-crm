import { PendientesView } from '@/components/pendientes/PendientesView';
import { getPendingSource } from '@/modules/pendientes/service';

export const dynamic = 'force-dynamic';

export default async function PendientesPage() {
    const [emisionServicios, siniestros] = await Promise.all([
        getPendingSource('emision-servicios'),
        getPendingSource('siniestros'),
    ]);

    return (
        <div className="flex h-full flex-col p-8">
            <h1 className="mb-4 text-2xl font-bold text-white">Pendientes</h1>
            <div className="min-h-0 flex-1">
                <PendientesView emisionServicios={emisionServicios} siniestros={siniestros} />
            </div>
        </div>
    );
}
