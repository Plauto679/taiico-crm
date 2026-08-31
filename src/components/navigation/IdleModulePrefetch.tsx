'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { prefetchRoute } from './SmartLink';

const FREQUENT_MODULES = [
  { href: '/pendientes', module: 'pendientes' },
  { href: '/renovaciones', module: 'renovaciones' },
  { href: '/cobranza', module: 'cobranza' },
  { href: '/clientes', module: 'clientes' },
  { href: '/agentes', module: 'agentes' },
  { href: '/cotizaciones', module: 'cotizaciones' },
  { href: '/finanzas', module: 'finanzas' },
];

type ConnectionLike = { saveData?: boolean; effectiveType?: string };

export function IdleModulePrefetch({ permissions }: { permissions: Record<string, string> | null }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!permissions) return;
    const connection = (navigator as Navigator & { connection?: ConnectionLike }).connection;
    if (connection?.saveData || connection?.effectiveType === '2g' || connection?.effectiveType === 'slow-2g') return;

    const routes = FREQUENT_MODULES
      .filter(({ module, href }) => ['lectura', 'operacion'].includes(permissions[module] || '') && href !== pathname)
      .slice(0, 4);
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    const run = () => routes.forEach(({ href }, index) => {
      timers.push(setTimeout(() => prefetchRoute(router, href), index * 700));
    });

    let idleId: number | undefined;
    if ('requestIdleCallback' in window) {
      idleId = window.requestIdleCallback(run, { timeout: 2500 });
    } else {
      timers.push(setTimeout(run, 1200));
    }
    return () => {
      timers.forEach(clearTimeout);
      if (idleId !== undefined) window.cancelIdleCallback(idleId);
    };
  }, [pathname, permissions, router]);

  return null;
}
