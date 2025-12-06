import { getUpcomingRenewals } from '@/modules/renovaciones/service';
import { RenovacionesView } from '@/components/renovaciones/RenovacionesView';

export const dynamic = 'force-dynamic';

export default async function RenovacionesPage({
    searchParams,
}: {
    searchParams: { insurer?: string };
}) {
    // Default to 30 days as requested (removing the buttons)
    const days = 30;
    const insurer = searchParams.insurer || 'Metlife';

    // Fetch both datasets
    const [vidaRenewals, gmmRenewals] = await Promise.all([
        getUpcomingRenewals(days, 'VIDA', insurer),
        getUpcomingRenewals(days, 'GMM', insurer)
    ]);

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <h1 className="text-2xl font-bold text-gray-900">Renovaciones</h1>

                {/* Insurer Selector */}
                <div className="inline-flex rounded-md shadow-sm" role="group">
                    {['Metlife', 'SURA', 'AXA', 'AARCO'].map((ins) => (
                        <a
                            key={ins}
                            href={`?insurer=${ins}`}
                            className={`px-4 py-2 text-sm font-medium border border-gray-200 first:rounded-l-lg last:rounded-r-lg ${insurer === ins ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 hover:bg-gray-100'}`}
                        >
                            {ins}
                        </a>
                    ))}
                </div>
            </div>

            <RenovacionesView vidaRenewals={vidaRenewals} gmmRenewals={gmmRenewals} />
        </div>
    );
}
