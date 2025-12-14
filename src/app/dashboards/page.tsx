import { getCobranzaVida, getCobranzaGMM } from '@/modules/cobranza/service';
import { DashboardsView } from '@/components/dashboards/DashboardsView';
import { DateRangeFilter } from '@/components/ui/DateRangeFilter';
import { CobranzaVida, CobranzaGMM, CobranzaSura, CobranzaAarco } from '@/lib/types/cobranza';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function DashboardsPage({
    searchParams,
}: {
    searchParams: Promise<{ insurer?: string; startDate?: string; endDate?: string }>;
}) {
    const params = await searchParams;
    const insurer = params.insurer || 'Metlife';
    const startDate = params.startDate;
    const endDate = params.endDate;

    let vidaData: CobranzaVida[] = [];
    let gmmData: CobranzaGMM[] = [];
    let suraData: CobranzaSura[] = [];
    let aarcoData: CobranzaAarco[] = [];

    if (insurer === 'Metlife') {
        vidaData = await getCobranzaVida(startDate, endDate, insurer) as CobranzaVida[];
        gmmData = await getCobranzaGMM(startDate, endDate, insurer) as CobranzaGMM[];
    } else if (insurer === 'SURA') {
        suraData = await getCobranzaVida(startDate, endDate, insurer) as CobranzaSura[];
    } else if (insurer === 'AARCO_AXA') {
        aarcoData = (await getCobranzaVida(startDate, endDate, insurer)) as unknown as CobranzaAarco[];
    }

    return (
        <div className="flex flex-col h-full bg-gray-50/50">
            <div className="flex-none p-8 pb-4 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <h1 className="text-2xl font-bold text-gray-900">Dashboards</h1>

                    <div className="inline-flex rounded-md shadow-sm" role="group">
                        {['Metlife', 'SURA', 'AARCO_AXA'].map((ins) => {
                            const label = ins === 'AARCO_AXA' ? 'AARCO & AXA' : ins;
                            return (
                                <Link
                                    key={ins}
                                    href={`?insurer=${ins}${startDate ? `&startDate=${startDate}` : ''}${endDate ? `&endDate=${endDate}` : ''}`}
                                    className={`px-4 py-2 text-sm font-medium border border-gray-200 first:rounded-l-lg last:rounded-r-lg ${insurer === ins ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 hover:bg-gray-100'}`}
                                >
                                    {label}
                                </Link>
                            );
                        })}
                    </div>
                </div>

                <DateRangeFilter />
            </div>

            <div className="flex-1 min-h-0 px-8 pb-8 overflow-y-auto">
                <DashboardsView
                    vidaData={vidaData}
                    gmmData={gmmData}
                    suraData={suraData}
                    aarcoData={aarcoData}
                    insurer={insurer}
                />
            </div>
        </div>
    );
}
