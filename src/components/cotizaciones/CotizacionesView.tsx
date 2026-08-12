'use client';

import { useEffect, useMemo, useState } from 'react';
import { FileText, Loader2, Plus, Search, UserRoundPlus, X } from 'lucide-react';
import {
  createQuote,
  searchQuoteClients,
  type Quote,
  type QuoteClient,
} from '@/modules/cotizaciones/service';

type Props = {
  initialQuotes: Quote[];
  products: Record<string, string[]>;
};

export function CotizacionesView({ initialQuotes, products }: Props) {
  const [quotes, setQuotes] = useState(initialQuotes);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [clients, setClients] = useState<QuoteClient[]>([]);
  const [selected, setSelected] = useState<QuoteClient | null>(null);
  const [prospect, setProspect] = useState(false);
  const [prospectName, setProspectName] = useState('');
  const [ramo, setRamo] = useState('GMM');
  const [producto, setProducto] = useState(products.GMM?.[0] || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open || selected || prospect || query.trim().length < 2) {
      setClients([]);
      return;
    }
    const timer = window.setTimeout(() => {
      searchQuoteClients(query).then(setClients).catch(() => setClients([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [open, query, selected, prospect]);

  const availableProducts = useMemo(() => products[ramo] || [], [products, ramo]);

  function reset() {
    setQuery('');
    setClients([]);
    setSelected(null);
    setProspect(false);
    setProspectName('');
    setRamo('GMM');
    setProducto(products.GMM?.[0] || '');
    setError('');
  }

  async function submit() {
    setSaving(true);
    setError('');
    try {
      const quote = await createQuote({
        client_id: selected?.id,
        prospect_name: prospect ? prospectName : undefined,
        ramo,
        producto,
      });
      setQuotes((current) => [...current, quote]);
      setOpen(false);
      reset();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message.replace('API Error: ', '') : 'No se pudo registrar');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between rounded-xl bg-white p-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Control de cotizaciones</h2>
          <p className="text-sm text-slate-500">Registros sincronizados con Cotizaciones.xlsx</p>
        </div>
        <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white shadow hover:bg-blue-700">
          <Plus className="h-5 w-5" /> Cotizar
        </button>
      </div>

      <div className="overflow-hidden rounded-xl bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>{['Folio', 'Cliente / Prospecto', 'RFC', 'Ramo', 'Producto', 'Estatus', 'Cotizaciones'].map((header) => <th key={header} className="px-4 py-3">{header}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {quotes.map((quote) => (
                <tr key={quote.id} className="hover:bg-blue-50/40">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{quote.id}</td>
                  <td className="px-4 py-3">{quote.cliente}</td>
                  <td className="whitespace-nowrap px-4 py-3">{quote.rfc || 'Prospecto'}</td>
                  <td className="px-4 py-3">{quote.ramo}</td>
                  <td className="px-4 py-3">{quote.producto}</td>
                  <td className="px-4 py-3"><span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">{quote.estatus}</span></td>
                  <td className="px-4 py-3">{quote.cotizaciones ? <a className="text-blue-600 hover:underline" href={quote.cotizaciones} target="_blank" rel="noreferrer">Abrir carpeta</a> : <span className="text-slate-400">Pendiente</span>}</td>
                </tr>
              ))}
              {!quotes.length && <tr><td colSpan={7} className="px-6 py-16 text-center text-slate-500"><FileText className="mx-auto mb-3 h-9 w-9 text-slate-300" />Aún no hay cotizaciones registradas.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="flex items-start justify-between border-b px-6 py-5">
              <div><h2 className="text-xl font-bold text-slate-900">Nueva cotización</h2><p className="mt-1 text-sm text-slate-500">Primero identifica al cliente; después elige ramo y producto.</p></div>
              <button onClick={() => { setOpen(false); reset(); }} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-6 p-6">
              {!selected && !prospect ? (
                <section className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Buscar cliente por nombre o RFC</label>
                  <div className="relative"><Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ej. AAMA950203I52 o Alberto Alfaro" className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" /></div>
                  {!!clients.length && <div className="max-h-52 divide-y overflow-y-auto rounded-lg border">{clients.map((client) => <button key={client.id} onClick={() => setSelected(client)} className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-blue-50"><span className="font-medium text-slate-800">{client.nombre}</span><span className="text-sm text-slate-500">{client.rfc || 'Sin RFC'}</span></button>)}</div>}
                  {query.trim().length >= 2 && !clients.length && <p className="text-sm text-slate-500">No encontramos coincidencias. Puedes registrar la cotización como prospecto.</p>}
                  <button onClick={() => { setProspect(true); setProspectName(query.trim()); }} className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-800"><UserRoundPlus className="h-4 w-4" /> No existe: crear prospecto</button>
                </section>
              ) : (
                <section className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">{selected ? 'Cliente existente' : 'Prospecto nuevo'}</p>
                  {prospect ? <input value={prospectName} onChange={(event) => setProspectName(event.target.value)} placeholder="Nombre completo del prospecto" className="mt-2 w-full rounded-lg border border-blue-200 bg-white px-3 py-2.5 text-slate-900" /> : <><p className="mt-1 font-semibold text-slate-900">{selected?.nombre}</p><p className="text-sm text-slate-600">RFC: {selected?.rfc}</p></>}
                  <button onClick={() => { setSelected(null); setProspect(false); }} className="mt-2 text-xs font-semibold text-blue-700 hover:underline">Cambiar cliente</button>
                </section>
              )}

              {(selected || prospect) && <div className="grid gap-5 sm:grid-cols-2">
                <label className="space-y-2 text-sm font-semibold text-slate-700">Ramo<select value={ramo} onChange={(event) => { const next = event.target.value; setRamo(next); setProducto(products[next]?.[0] || ''); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900"><option>GMM</option><option>Vida</option></select></label>
                <label className="space-y-2 text-sm font-semibold text-slate-700">Producto<select value={producto} onChange={(event) => setProducto(event.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 font-normal text-slate-900">{availableProducts.map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>}
              {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t bg-slate-50 px-6 py-4"><button onClick={() => { setOpen(false); reset(); }} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-200">Cancelar</button><button disabled={saving || (!selected && !prospect) || (prospect && prospectName.trim().length < 2)} onClick={submit} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{saving && <Loader2 className="h-4 w-4 animate-spin" />} Registrar cotización</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
