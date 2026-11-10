import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import { HelpCenter } from '@/components/ayuda/HelpCenter';
import { availableHelp, type HelpSession } from '@/lib/help-catalog';

export const dynamic = 'force-dynamic';
export default async function HelpPage() {
  const jar = await cookies();
  const response = await fetch(`${process.env.INTERNAL_API_BASE_URL || 'http://127.0.0.1:7777'}/session`, {
    headers: { Cookie: jar.toString() }, cache: 'no-store',
  });
  if (response.status === 401) redirect('/login');
  if (response.status === 403) redirect('/sin-acceso');
  if (!response.ok) throw new Error('No fue posible consultar tu acceso. Intenta de nuevo.');
  const session: HelpSession = await response.json();
  return <HelpCenter guides={availableHelp(session)} />;
}
