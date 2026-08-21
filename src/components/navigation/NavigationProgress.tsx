'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

type NavigationState = 'idle' | 'loading' | 'complete';

export function NavigationProgress() {
  const pathname = usePathname();
  const [state, setState] = useState<NavigationState>('idle');
  const startedRef = useRef(false);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const start = () => {
      startedRef.current = true;
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      setState('loading');
    };
    window.addEventListener('taiico:navigation-start', start);
    return () => window.removeEventListener('taiico:navigation-start', start);
  }, []);

  useEffect(() => {
    if (!startedRef.current) return;
    startedRef.current = false;
    setState('complete');
    hideTimerRef.current = setTimeout(() => setState('idle'), 900);
    return () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [pathname]);

  if (state === 'idle') return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[100]" aria-live="polite">
      <div className="h-1 overflow-hidden bg-blue-100/70">
        <div
          className={`h-full bg-blue-600 shadow-[0_0_10px_rgba(37,99,235,0.65)] transition-all duration-500 ${state === 'complete' ? 'w-full' : 'w-4/5 animate-pulse'}`}
        />
      </div>
      <div className="absolute right-3 top-3 rounded-full bg-white/95 px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-lg ring-1 ring-slate-200">
        {state === 'complete' ? 'Módulo actualizado' : 'Cargando módulo…'}
      </div>
    </div>
  );
}
