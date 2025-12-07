import { getCobranzaVida, getCobranzaGMM } from '@/modules/cobranza/service';
import { CobranzaView } from '@/components/cobranza/CobranzaView';
import { DateRangeFilter } from '@/components/ui/DateRangeFilter';

export const dynamic = 'force-dynamic';

export default async function CobranzaPage({
    searchParams,
}: {
    searchParams: { startDate?: string; endDate?: string };
}) {
    const startDate = searchParams.startDate;
    const endDate = searchParams.endDate;

    const vidaData = await getCobranzaVida(startDate, endDate);
    const gmmData = await getCobranzaGMM(startDate, endDate);

    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4 space-y-4">
                <h1 className="text-2xl font-bold text-gray-900">Cobranza</h1>
                <DateRangeFilter />
            </div>
            <div className="flex-1 min-h-0 px-8 pb-8">
                <CobranzaView vidaData={vidaData} gmmData={gmmData} />
            </div>
        </div>
    );
}
