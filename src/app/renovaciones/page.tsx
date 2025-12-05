import { getUpcomingRenewals } from '@/modules/renovaciones/service';
import { DataTable } from '@/components/ui/DataTable';
import { RenewalItem } from '@/lib/types/renovaciones';

export const dynamic = 'force-dynamic';

export default async function RenovacionesPage({
    searchParams,
}: {
    searchParams: { days?: string };
}) {
    const days = searchParams.days ? parseInt(searchParams.days) : 30;
    const renewals = await getUpcomingRenewals(days);

    const columns = [
        { header: 'Póliza', accessorKey: 'poliza' as keyof RenewalItem },
        { header: 'Contratante', accessorKey: 'contratante' as keyof RenewalItem },
        {
            header: 'Fecha Renovación',
            accessorKey: (row: RenewalItem) => {
                if (!row.fechaRenovacion) return 'N/A';
                if (typeof row.fechaRenovacion === 'string') return row.fechaRenovacion;
                return row.fechaRenovacion.toLocaleDateString('es-MX');
            }
        },
        { header: 'Ramo', accessorKey: 'ramo' as keyof RenewalItem },
        { header: 'Agente', accessorKey: 'agente' as keyof RenewalItem },
        { header: 'Estatus', accessorKey: 'estatus' as keyof RenewalItem },
        {
            header: 'Prima',
            accessorKey: (row: RenewalItem) => row.prima ? `$${row.prima.toLocaleString('es-MX')}` : 'N/A'
        },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-gray-900">Renovaciones</h1>
                <div className="space-x-2">
                    <a href="?days=30" className={`px-3 py-1 rounded-md text-sm ${days === 30 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}>30 Días</a>
                    <a href="?days=60" className={`px-3 py-1 rounded-md text-sm ${days === 60 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}>60 Días</a>
                    <a href="?days=90" className={`px-3 py-1 rounded-md text-sm ${days === 90 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}>90 Días</a>
                </div>
            </div>
            <DataTable data={renewals} columns={columns} />
        </div>
    );
}
