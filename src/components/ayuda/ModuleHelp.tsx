'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { CircleHelp } from 'lucide-react';
import { availableHelp, guideForPath, type HelpGuide, type HelpSession } from '@/lib/help-catalog';
import { HelpDialog } from './HelpDialog';

export function ModuleHelp() {
  const pathname = usePathname();
  const guide = guideForPath(pathname);
  return guide ? <ModuleHelpButton key={pathname} guide={guide} /> : null;
}
function ModuleHelpButton({ guide }: { guide: HelpGuide }) {
  const [allowed, setAllowed] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = () => fetch('/api/session', { cache: 'no-store', credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : null)
      .then((session: HelpSession | null) => { if (active) { const permitted = !!session && availableHelp(session).some(item => item.id === guide.id); setAllowed(permitted); if (!permitted) setOpen(false); } })
      .catch(() => { if (active) { setAllowed(false); setOpen(false); } });
    void refresh();
    window.addEventListener('focus', refresh);
    return () => { active = false; window.removeEventListener('focus', refresh); };
  }, [guide.id]);
  if (!allowed) return null;
  return <div className="flex min-h-14 shrink-0 items-center justify-end border-b border-white/15 bg-[#284965] py-2 pl-16 pr-4">
    <button onClick={() => setOpen(true)} aria-haspopup="dialog" className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-white hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-white"><CircleHelp className="h-5 w-5" aria-hidden="true" />¿Cómo usar este módulo?</button>
    {open && <HelpDialog guide={guide} onClose={() => setOpen(false)} />}
  </div>;
}
