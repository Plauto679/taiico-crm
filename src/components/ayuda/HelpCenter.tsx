'use client';

import { useState } from 'react';
import Link from 'next/link';
import { BookOpen, Search } from 'lucide-react';
import type { HelpGuide } from '@/lib/help-catalog';
import { HelpDialog } from './HelpDialog';

const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
export function HelpCenter({ guides }: { guides: HelpGuide[] }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<HelpGuide | null>(null);
  const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
  const filtered = guides.filter(guide => terms.every(term => normalize([guide.title, guide.purpose, ...guide.steps, guide.result, ...guide.notes].join(' ')).includes(term)));
  return <div className="h-full overflow-y-auto p-4 pt-16 text-slate-800 md:p-8">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="text-white"><div className="mb-2 flex items-center gap-3"><BookOpen aria-hidden="true" className="h-7 w-7" /><h1 className="text-3xl font-bold">Ayuda</h1></div><p>Aprende a usar tus módulos, paso a paso.</p><p className="mt-2 text-sm text-blue-100">También puedes consultar estas guías desde “¿Cómo usar este módulo?” sin salir de tu trabajo.</p></header>
      <div className="rounded-2xl bg-white p-5"><label htmlFor="help-search" className="mb-2 block font-semibold">Buscar un módulo o una tarea</label><div className="flex items-center gap-3 rounded-lg border border-slate-300 px-3 focus-within:ring-2 focus-within:ring-sky-700"><Search aria-hidden="true" className="h-5 w-5 shrink-0 text-slate-500" /><input id="help-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Ej. reembolso, cargar bases, enviar correo" className="min-w-0 flex-1 bg-white py-3 outline-none" /></div><p className="mt-3 text-sm text-slate-600" role="status">{filtered.length} guías disponibles con tu acceso actual.</p></div>
      {filtered.length === 0 && <div className="rounded-xl bg-white p-6"><p className="font-semibold">No encontramos una guía con esa búsqueda.</p><p className="mt-2">Prueba con el nombre del módulo o una palabra más general.</p><button onClick={() => setQuery('')} className="mt-3 font-semibold text-sky-800 underline">Limpiar búsqueda</button></div>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{filtered.map(guide => <article key={guide.id} className="flex flex-col rounded-2xl bg-white p-5 shadow-sm"><h2 className="text-lg font-bold">{guide.title}</h2><p className="mb-5 mt-2 flex-1 text-sm leading-relaxed text-slate-600">{guide.purpose}</p><div className="flex flex-wrap items-center gap-4"><button onClick={() => setSelected(guide)} aria-haspopup="dialog" aria-label={`Ver guía de ${guide.title}`} className="rounded-lg bg-sky-900 px-4 py-2 font-semibold text-white hover:bg-sky-800">Ver guía</button><Link href={guide.href} className="text-sm font-semibold text-sky-800 underline">Ir al módulo</Link></div></article>)}</div>
    </div>
    {selected && <HelpDialog guide={selected} onClose={() => setSelected(null)} />}
  </div>;
}
