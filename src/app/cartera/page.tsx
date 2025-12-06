import { getClientProfile } from '@/modules/cartera/service';
import { CarteraSearch } from '@/components/cartera/CarteraSearch';
import { ClientProfile } from '@/lib/types/cartera';

export const dynamic = 'force-dynamic';

export default async function CarteraPage({
    searchParams,
}: {
    searchParams: { q?: string };
}) {
    const query = searchParams.q || '';
    const profiles = query ? await getClientProfile(query) : [];

    return (
    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4 space-y-6">
                <h1 className="text-2xl font-bold text-gray-900">Cartera de Clientes</h1>
                <CarteraSearch />
            </div>

            <div className="flex-1 min-h-0 px-8 pb-8 overflow-y-auto">
                <div className="space-y-4">
                    {profiles.length === 0 ? (
                        <div className="text-center text-gray-500 py-8">
                            {query ? 'No se encontraron resultados.' : 'Ingrese una búsqueda para ver resultados.'}
                        </div>
                    ) : (
                        profiles.map((profile) => (
                            <div key={profile.id} className="rounded-lg border bg-white p-6 shadow-sm">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <h3 className="text-lg font-semibold text-gray-900">{profile.nombre}</h3>
                                        <p className="text-sm text-gray-500">Prospectador: {profile.prospectador}</p>
                                    </div>
                                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                                        {profile.polizas[0].ramo}
                                    </span>
                                </div>
                                <div className="mt-4">
                                    <h4 className="text-sm font-medium text-gray-700">Pólizas</h4>
                                    <ul className="mt-2 divide-y divide-gray-200">
                                        {profile.polizas.map((poliza, idx) => (
                                            <li key={idx} className="py-2 flex justify-between text-sm">
                                                <span className="text-gray-600">#{poliza.numero}</span>
                                                <span className="text-gray-500">{poliza.estatus}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
    );
}
