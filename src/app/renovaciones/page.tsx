import { getUpcomingRenewals } from '@/modules/renovaciones/service';
import { RenovacionesView } from '@/components/renovaciones/RenovacionesView';
import { DateRangeFilter } from '@/components/ui/DateRangeFilter';
import { RenovacionGMM, RenovacionVida, RenovacionSura } from '@/lib/types/renovaciones';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function RenovacionesPage({
    searchParams,
}: {
    searchParams: Promise<{ insurer?: string; startDate?: string; endDate?: string }>;
}) {
    // Await searchParams for Next.js 15+
    const params = await searchParams;

    // Default to 30 days as requested (removing the buttons)
    const days = 30;
    const insurer = params.insurer || 'Metlife';
    const startDate = params.startDate;
    const endDate = params.endDate;

    let vidaRenewals: RenovacionVida[] = [];
    let gmmRenewals: RenovacionGMM[] = [];
    let suraRenewals: RenovacionSura[] = [];

    if (insurer === 'Metlife') {
        const [vida, gmm] = await Promise.all([
            getUpcomingRenewals(days, 'VIDA', insurer, startDate, endDate) as Promise<RenovacionVida[]>,
            getUpcomingRenewals(days, 'GMM', insurer, startDate, endDate) as Promise<RenovacionGMM[]>
        ]);
        vidaRenewals = vida;
        gmmRenewals = gmm;
    } else if (insurer === 'SURA') {
        // For SURA we fetch 'ALL' or just default since we handle it as one block in backend
        suraRenewals = (await getUpcomingRenewals(days, 'ALL', insurer, startDate, endDate)) as RenovacionSura[];
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex-none p-8 pb-4 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <h1 className="text-2xl font-bold text-gray-900">Renovaciones</h1>

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

                {/* Date Filter */}
                <DateRangeFilter />
            </div>

            <div className="flex-1 min-h-0 px-8 pb-8">
                <RenovacionesView
                    vidaRenewals={vidaRenewals}
                    gmmRenewals={gmmRenewals}
                    suraRenewals={suraRenewals}
                    insurer={insurer}
                />
            </div>
        </div>
    );
}
