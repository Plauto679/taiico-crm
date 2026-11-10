'use client';

import { useEffect, useId, useRef } from 'react';
import Link from 'next/link';
import { X } from 'lucide-react';
import type { HelpGuide } from '@/lib/help-catalog';

export function HelpDialog({ guide, onClose }: { guide: HelpGuide; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => { element?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={dialog} aria-labelledby={titleId} onClose={onClose}
    onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex="0"]')).filter(element => !element.hasAttribute('disabled'));
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}
    className="m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-2xl bg-white p-0 text-slate-800 shadow-2xl backdrop:bg-slate-950/60">
    <header className="sticky top-0 flex items-start justify-between gap-4 border-b bg-white p-5">
      <div><p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Guía de uso</p><h2 id={titleId} className="text-xl font-bold">{guide.title}</h2></div>
      <button autoFocus onClick={onClose} aria-label="Cerrar ayuda" className="rounded-lg p-2 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-sky-700"><X aria-hidden="true" /></button>
    </header>
    <div className="space-y-6 p-5 sm:p-6">
      <p>{guide.purpose}</p>
      <section><h3 className="mb-3 font-bold">Paso a paso</h3><ol className="list-decimal space-y-3 pl-5">{guide.steps.map(step => <li key={step} className="pl-1 leading-relaxed">{step}</li>)}</ol></section>
      <section className="rounded-xl bg-sky-50 p-4"><h3 className="mb-2 font-bold">Qué obtienes</h3><p>{guide.result}</p></section>
      <section><h3 className="mb-3 font-bold">Ten en cuenta</h3><ul className="list-disc space-y-2 pl-5">{guide.notes.map(note => <li key={note}>{note}</li>)}</ul></section>
      <p className="border-t pt-4 text-sm text-slate-600">Las acciones disponibles dependen de tus permisos. Con acceso de lectura puedes consultar; los cambios y envíos requieren los permisos correspondientes. Si no puedes continuar, revisa el aviso de la pantalla y contacta al administrador indicando el módulo y el paso.</p>
      <div className="flex flex-wrap gap-3"><Link href="/ayuda" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-sky-800">Todas las guías</Link><button onClick={onClose} className="rounded-lg bg-sky-900 px-4 py-2 font-semibold text-white">Entendido</button></div>
    </div>
  </dialog>;
}
