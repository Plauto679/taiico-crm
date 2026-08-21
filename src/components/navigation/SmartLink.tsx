'use client';

import Link from 'next/link';
import type { ComponentProps } from 'react';
import { useCallback } from 'react';
import { useRouter } from 'next/navigation';

const prefetchedRoutes = new Set<string>();

export function prefetchRoute(router: ReturnType<typeof useRouter>, href: string) {
  if (prefetchedRoutes.has(href)) return;
  prefetchedRoutes.add(href);
  router.prefetch(href);
}

type SmartLinkProps = ComponentProps<typeof Link>;

export function SmartLink({
  href,
  onMouseEnter,
  onFocus,
  onTouchStart,
  onClick,
  ...props
}: SmartLinkProps) {
  const router = useRouter();
  const route = typeof href === 'string' ? href : href.pathname || '/';
  const prefetch = useCallback(() => prefetchRoute(router, route), [router, route]);

  return (
    <Link
      href={href}
      prefetch
      onMouseEnter={(event) => {
        prefetch();
        onMouseEnter?.(event);
      }}
      onFocus={(event) => {
        prefetch();
        onFocus?.(event);
      }}
      onTouchStart={(event) => {
        prefetch();
        onTouchStart?.(event);
      }}
      onClick={(event) => {
        const target = event.currentTarget.target;
        const isModified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
        if (!event.defaultPrevented && !isModified && target !== '_blank') {
          const nextUrl = new URL(route, window.location.origin);
          const currentUrl = `${window.location.pathname}${window.location.search}`;
          if (`${nextUrl.pathname}${nextUrl.search}` !== currentUrl) {
            window.dispatchEvent(new CustomEvent('taiico:navigation-start'));
          }
        }
        onClick?.(event);
      }}
      {...props}
    />
  );
}
