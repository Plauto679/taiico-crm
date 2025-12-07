import { getCobranzaVida, getCobranzaGMM } from '@/modules/cobranza/service';
import { CobranzaView } from '@/components/cobranza/CobranzaView';
import { DateRangeFilter } from '@/components/ui/DateRangeFilter';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function CobranzaPage({
    searchParams,
}: {
    searchParams: Promise<{ insurer?: string; startDate?: string; endDate?: string }>;
}) {
    const params = await searchParams;
    const insurer = params.insurer || 'Metlife';
    const startDate = params.startDate;
    const endDate = params.endDate;

    // Currently we only fetch Metlife data regardless of the selected insurer
    // This will be updated later to support other insurers
    const vidaData = await getCobranzaVida(startDate, endDate);
    const gmmData = await getCobranzaGMM(startDate, endDate);

    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <h1 className="text-2xl font-bold text-gray-900">Cobranza</h1>

                    {/* Insurer Selector */}
                    <div className="inline-flex rounded-md shadow-sm" role="group">
                        {['Metlife', 'SURA', 'AXA', 'AARCO'].map((ins) => (
                            <Link
                                key={ins}
                                href={`?insurer=${ins}${startDate ? `&startDate=${startDate}` : ''}${endDate ? `&endDate=${endDate}` : ''}`}
                                className={`px-4 py-2 text-sm font-medium border border-gray-200 first:rounded-l-lg last:rounded-r-lg ${insurer === ins ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 hover:bg-gray-100'}`}
                            >
                                {ins}
                            </Link>
                        ))}
                    </div>
                </div>

                <DateRangeFilter />
            </div>
            <div className="flex-1 min-h-0 px-8 pb-8">
                <CobranzaView vidaData={vidaData} gmmData={gmmData} />
            </div>
        </div>
    );
}
