import { CotizacionesView } from '@/components/cotizaciones/CotizacionesView';
import { getQuoteConfig, getQuotes } from '@/modules/cotizaciones/service';

export default async function CotizacionesPage() {
  const [quotes, config] = await Promise.all([getQuotes(), getQuoteConfig()]);
  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <div><h1 className="text-3xl font-bold text-white">Cotizaciones</h1><p className="mt-1 text-blue-100">Inicia y da seguimiento a cotizaciones de MetLife.</p></div>
        <CotizacionesView initialQuotes={quotes} products={config.products} />
      </div>
    </div>
  );
}
