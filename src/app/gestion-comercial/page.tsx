import Link from 'next/link';
import { CommercialBoard } from '@/components/gestion-comercial/CommercialBoard';
import { getCommercialConfig, getCommercialPipeline } from '@/modules/gestion-comercial/service';

export const dynamic = 'force-dynamic';

export default async function GestionComercialPage() {
  const [pipeline, config] = await Promise.all([getCommercialPipeline(), getCommercialConfig()]);
  return (
    <div className="flex h-full min-h-0 flex-col gap-5 overflow-hidden p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-white md:text-3xl">Gestión Comercial</h1>
                <Link href="/captacion?tipo=clientes" className="mt-2 inline-block rounded-lg bg-white px-4 py-2 text-sm font-semibold text-[#34587c]">Leads web · Taiico →</Link>
        <p className="mt-1 text-sm text-blue-100">Oportunidades, responsables y valor esperado del funnel.</p>
      </div>
      <CommercialBoard initialPipeline={pipeline} config={config} />
    </div>
  );
}
