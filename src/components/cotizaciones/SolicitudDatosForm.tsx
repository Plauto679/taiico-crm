'use client';

import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ExternalLink, Loader2, Upload } from 'lucide-react';
import { getQuoteDataRequest, submitQuoteDataRequest, type QuoteDataRequestPublic } from '@/modules/cotizaciones/service';

type Props = {
  token: string;
};

const initialFields = {
  nombre_completo: '',
  rfc: '',
  curp: '',
  fecha_nacimiento: '',
  correo: '',
  telefono: '',
  domicilio: '',
  ocupacion: '',
  forma_pago: '',
  beneficiarios: '',
  comentarios: '',
};

export function SolicitudDatosForm({ token }: Props) {
  const [request, setRequest] = useState<QuoteDataRequestPublic | null>(null);
  const [fields, setFields] = useState(initialFields);
  const [documents, setDocuments] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState<{ folder_link: string; notification_warning?: string | null } | null>(null);

  useEffect(() => {
    let active = true;
    getQuoteDataRequest(token)
      .then((response) => {
        if (!active) return;
        setRequest(response);
        setFields((current) => ({
          ...current,
          nombre_completo: response.quote.cliente || current.nombre_completo,
          rfc: response.quote.rfc || current.rfc,
        }));
      })
      .catch((exception) => {
        if (active) setError(exception instanceof Error ? exception.message : 'No fue posible leer la solicitud');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  const disabled = useMemo(() => {
    return !fields.nombre_completo.trim() || !fields.rfc.trim() || !fields.correo.trim() || !fields.telefono.trim();
  }, [fields]);

  function updateField(name: keyof typeof initialFields, value: string) {
    setFields((current) => ({ ...current, [name]: value }));
  }

  async function submit() {
    setSubmitting(true);
    setError('');
    try {
      const result = await submitQuoteDataRequest(token, fields, documents);
      setSuccess({ folder_link: result.folder_link, notification_warning: result.notification_warning });
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : 'No fue posible enviar la solicitud');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
        <div className="flex items-center gap-3 rounded-2xl bg-white p-6 text-slate-600 shadow">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          Cargando solicitud…
        </div>
      </main>
    );
  }

  if (!request || error && !request) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
        <section className="w-full max-w-xl rounded-2xl bg-white p-8 text-center shadow">
          <img src="/logo.png" alt="TAIICO Life Advisors" className="mx-auto mb-5 h-20 w-auto" />
          <h1 className="text-2xl font-bold text-slate-900">Solicitud no disponible</h1>
          <p className="mt-3 text-slate-600">{error || 'La liga no existe o no se pudo validar.'}</p>
        </section>
      </main>
    );
  }

  if (request.expired || request.submitted || success) {
    return (
      <main className="min-h-screen bg-slate-100 p-6">
        <section className="mx-auto mt-10 w-full max-w-2xl rounded-2xl bg-white p-8 shadow">
          <img src="/logo.png" alt="TAIICO Life Advisors" className="mb-6 h-16 w-auto" />
          {success ? (
            <>
              <div className="flex items-center gap-3 text-emerald-700">
                <CheckCircle2 className="h-7 w-7" />
                <h1 className="text-2xl font-bold">Datos recibidos</h1>
              </div>
              <p className="mt-4 text-slate-600">Gracias. Recibimos tu información y notificamos al equipo correspondiente para continuar con la emisión.</p>
              {success.notification_warning && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{success.notification_warning}</p>}
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-slate-900">{request.expired ? 'La liga expiró' : 'Solicitud ya enviada'}</h1>
              <p className="mt-3 text-slate-600">{request.expired ? 'Solicita una nueva liga a tu asesor.' : 'Esta liga ya fue utilizada para enviar información.'}</p>
            </>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-100 p-4 sm:p-8">
      <section className="mx-auto w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-xl">
        <header className="bg-[#355f86] px-6 py-8 text-white sm:px-10">
          <img src="/logo.png" alt="TAIICO Life Advisors" className="mb-6 h-16 w-auto rounded-full bg-white/10 p-1" />
          <h1 className="text-3xl font-bold">Datos para solicitud de emisión de póliza</h1>
          <p className="mt-2 text-blue-100">Completa la información solicitada y anexa tus documentos. La liga vence el {new Date(request.expires_at).toLocaleString('es-MX')}.</p>
        </header>

        <div className="space-y-6 p-6 sm:p-10">
          <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-950">
            <p className="font-semibold">{request.quote.producto}</p>
            <p className="mt-1">Cliente/prospecto: {request.quote.cliente}</p>
            <p>RFC: {request.quote.rfc}</p>
            <p>Asesor: {request.quote.agente || 'TAIICO'}</p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <label className="space-y-2 text-sm font-semibold text-slate-700">Nombre completo<input value={fields.nombre_completo} onChange={(event) => updateField('nombre_completo', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">RFC<input value={fields.rfc} onChange={(event) => updateField('rfc', event.target.value.toUpperCase())} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal uppercase text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">CURP<input value={fields.curp} onChange={(event) => updateField('curp', event.target.value.toUpperCase())} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal uppercase text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">Fecha de nacimiento<input type="date" value={fields.fecha_nacimiento} onChange={(event) => updateField('fecha_nacimiento', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">Correo electrónico<input type="email" value={fields.correo} onChange={(event) => updateField('correo', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">Teléfono<input value={fields.telefono} onChange={(event) => updateField('telefono', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700 sm:col-span-2">Domicilio completo<textarea value={fields.domicilio} onChange={(event) => updateField('domicilio', event.target.value)} rows={3} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">Ocupación<input value={fields.ocupacion} onChange={(event) => updateField('ocupacion', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">Forma de pago preferida<input value={fields.forma_pago} onChange={(event) => updateField('forma_pago', event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700 sm:col-span-2">Beneficiarios / dependientes / datos adicionales<textarea value={fields.beneficiarios} onChange={(event) => updateField('beneficiarios', event.target.value)} rows={4} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
            <label className="space-y-2 text-sm font-semibold text-slate-700 sm:col-span-2">Comentarios<textarea value={fields.comentarios} onChange={(event) => updateField('comentarios', event.target.value)} rows={3} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 font-normal text-slate-900" /></label>
          </div>

          <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg bg-white p-6 text-center text-sm font-semibold text-blue-700 ring-1 ring-slate-200 hover:bg-blue-50">
              <Upload className="h-6 w-6" />
              Adjuntar documentos
              <span className="font-normal text-slate-500">Identificación, comprobante de domicilio u otros archivos requeridos.</span>
              <input type="file" multiple className="hidden" onChange={(event) => setDocuments(Array.from(event.target.files || []))} />
            </label>
            {!!documents.length && (
              <ul className="mt-4 space-y-2 text-sm text-slate-700">
                {documents.map((document) => <li key={`${document.name}-${document.size}`} className="rounded-lg bg-white px-3 py-2">{document.name}</li>)}
              </ul>
            )}
          </section>

          {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        </div>

        <footer className="flex flex-col gap-3 border-t bg-slate-50 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-10">
          <p className="text-xs text-slate-500">Tu información será enviada de forma segura al equipo de TAIICO para continuar la emisión.</p>
          <button disabled={submitting || disabled} onClick={submit} className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
            Enviar datos
          </button>
        </footer>
      </section>
    </main>
  );
}
