import { getCarteraData } from '@/modules/cartera/service';
import { CarteraView } from '@/components/cartera/CarteraView';

export const dynamic = 'force-dynamic';

export default async function CarteraPage({
    searchParams,
}: {
    searchParams: Promise<{ insurer?: string; type?: string }>;
}) {
    const resolvedParams = await searchParams;
    const insurer = resolvedParams.insurer || 'Metlife';
    const type = resolvedParams.type || (insurer === 'Metlife' ? 'VIDA' : 'ALL');

    const data = await getCarteraData(insurer, type);

    return (
        <div className="flex flex-col h-full p-8 space-y-6">
            <h1 className="text-2xl font-bold text-gray-900">Cartera de Clientes</h1>
            <div className="flex-1 min-h-0">
                <CarteraView data={data} insurer={insurer} type={type} />
            </div>
        </div>
    );
}
