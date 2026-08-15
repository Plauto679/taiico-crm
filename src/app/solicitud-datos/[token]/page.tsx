import { SolicitudDatosForm } from '@/components/cotizaciones/SolicitudDatosForm';

type Props = {
  params: Promise<{ token: string }>;
};

export default async function SolicitudDatosPage({ params }: Props) {
  const { token } = await params;
  return <SolicitudDatosForm token={token} />;
}
