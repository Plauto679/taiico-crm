'use client';

import { useSearchParams } from 'next/navigation';

export function RenewalInsurerLinks({ insurer, startDate, endDate, renewalType }: {
    insurer: string; startDate: string; endDate: string; renewalType: string;
}) {
    const current = useSearchParams();
    return <div className="hidden sm:flex max-w-full overflow-x-auto rounded-md shadow-sm" role="group" aria-label="Aseguradora">
        {['Metlife', 'SURA', 'AARCO_AXA', 'Promotoria SURA'].map(value => {
            const params = new URLSearchParams({
                insurer: value,
                startDate: current.get('startDate') || startDate,
                endDate: current.get('endDate') || endDate,
            });
            if (value === 'Metlife') params.set('renewalType', current.get('renewalType') || renewalType);
            return <a key={value} href={`/renovaciones?${params}`} aria-current={insurer === value ? 'page' : undefined}
                className={`shrink-0 px-4 py-2 text-sm font-medium border border-gray-200 first:rounded-l-lg last:rounded-r-lg ${insurer === value ? 'bg-blue-600 text-white' : 'bg-white text-gray-900 hover:bg-gray-100'}`}>
                {value === 'AARCO_AXA' ? 'AARCO & AXA' : value}
            </a>;
        })}
    </div>;
}
