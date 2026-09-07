import { PendientesView } from '@/components/pendientes/PendientesView';
import type { CommercialPendingData, PendingAccess, PendingSourceData } from '@/lib/types/pendientes';
import { getCommercialPending, getPendingSource } from '@/modules/pendientes/service';

export const dynamic = 'force-dynamic';

export default async function PendientesPage() {
    const [emisionResult, siniestrosResult, commercialResult] = await Promise.allSettled([
        getPendingSource('emision-servicios'),
        getPendingSource('siniestros'),
        getCommercialPending(),
    ]);

    logLoadFailure('Emisión y Servicios', emisionResult);
    logLoadFailure('Siniestros', siniestrosResult);
    logLoadFailure('Comerciales', commercialResult);

    const availableAccess = emisionResult.status === 'fulfilled'
        ? emisionResult.value.access
        : siniestrosResult.status === 'fulfilled'
            ? siniestrosResult.value.access
            : EMPTY_ACCESS;
    const emisionServicios = emisionResult.status === 'fulfilled'
        ? emisionResult.value
        : unavailableSource('emision-servicios', 'Emisión y Servicios', availableAccess);
    const siniestros = siniestrosResult.status === 'fulfilled'
        ? siniestrosResult.value
        : unavailableSource('siniestros', 'Siniestros', availableAccess);
    const commercial: CommercialPendingData = commercialResult.status === 'fulfilled'
        ? commercialResult.value
        : { source: 'commercial', title: 'Comerciales', rows: [] };

    return (
        <div className="flex h-full flex-col p-8">
            <h1 className="mb-4 text-2xl font-bold text-white">Pendientes</h1>
            <div className="min-h-0 flex-1">
                <PendientesView emisionServicios={emisionServicios} siniestros={siniestros} commercial={commercial} />
            </div>
        </div>
    );
}

const EMPTY_ACCESS: PendingAccess = {
    role: '',
    can_operate: false,
    promotorias: [],
    rfc: '',
    central_admin: false,
    agents: [],
    admins: [],
};

function unavailableSource(
    source: PendingSourceData['source'],
    title: string,
    availableAccess: PendingAccess,
): PendingSourceData {
    return {
        source,
        title,
        sheet_name: '',
        core_headers: [],
        latest_update_header: '',
        rows: [],
        access: { ...availableAccess, can_operate: false },
        inconsistencies: [],
        load_error: `La fuente de ${title} no está disponible en Google Drive. Las demás secciones continúan funcionando.`,
    };
}

function logLoadFailure(label: string, result: PromiseSettledResult<unknown>) {
    if (result.status === 'rejected') {
        console.error(`No fue posible cargar Pendientes · ${label}:`, result.reason);
    }
}
