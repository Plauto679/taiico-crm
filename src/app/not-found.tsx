'use client';

import { ArrowLeft, FileQuestion, Home } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function NotFound() {
  const router = useRouter();

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto p-6">
      <div className="w-full max-w-xl rounded-2xl bg-white p-10 text-center shadow-2xl">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-blue-100 text-blue-700">
          <FileQuestion className="h-10 w-10" />
        </div>
        <p className="mt-6 text-sm font-bold uppercase tracking-[0.25em] text-blue-600">Error 404</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Esta página no existe</h1>
        <p className="mx-auto mt-3 max-w-md text-slate-600">
          Es posible que la dirección esté incompleta, haya cambiado o la página haya sido eliminada.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => router.back()}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            Regresar
          </button>
          <button
            type="button"
            onClick={() => router.push('/')}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700"
          >
            <Home className="h-4 w-4" />
            Ir al inicio
          </button>
        </div>
      </div>
    </div>
  );
}
